"""Behavioral boundaries for baselines, source validation, questions and saving."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import build_opener, ProxyHandler, Request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import research_decisions as decisions
import prepare_research as prepare
import serve_workbench as service
import validate_transcript_ready as transcript

AS_OF = datetime(2026, 8, 30, tzinfo=timezone.utc)

def works(count=12):
    return {"schema_version": 2, "as_of": AS_OF.isoformat(), "records": [
        {"platform": "douyin", "content_id": f"synthetic-{i}", "author_id": "synthetic-author-a",
         "author_name": "同名作者", "content_type": "video", "collection_batch_id": "synthetic-batch",
         "published_at": (AS_OF-timedelta(days=8+i)).isoformat(),
         "collected_at": AS_OF.isoformat(), "like_count": 100 if i else 1000,
         "view_count": 0, "view_count_reliable": False, "follower_count": 1500,
         "topic_id": "synthetic-topic", "qualified": i==0}
        for i in range(count)]}

def writing_state():
    return {"schema_version":2, "record_type":"writing_workbench","task_id":"synthetic-task","title":"合成稿",
        "revision":1,"sources":[{"source_id":"s","title":"原文","text":"整理交给工具，判断由人负责。"}],
        "sections":[{"id":"1","title":"核心判断","mine":"整理交给工具，判断由人负责。","note":"保留",
          "locked":False,"references":[{"source_id":"s","quote":"整理交给工具，判断由人负责。"}],
          "reviewed_text":"整理交给工具，判断由人负责。","analysis_status":"reviewed",
          "semantic_groups":[],"history":[]}],"history":[]}

class BaselineTests(unittest.TestCase):
    def test_excludes_target_and_uses_exact_median(self):
        data=decisions.calculate_baselines(works())
        target=data["records"][0]["baseline"]
        self.assertEqual((target["metric"],target["median"],target["ratio"]),("like_count",100,10))
        self.assertNotIn("synthetic-0",target["sample_ids"])
        self.assertEqual(target["sample_count"],11)

    def test_isolates_platform_author_type_and_batch(self):
        for field,value in [("platform","bilibili"),("author_id","synthetic-author-b"),("content_type","image"),("collection_batch_id","synthetic-next")]:
            data=works(11); copy=deepcopy(data["records"][0]);copy["content_id"]="synthetic-other";copy[field]=value
            data["records"].append(copy)
            result=decisions.calculate_baselines(data)
            self.assertEqual(result["records"][-1]["baseline"]["reason"],"insufficient_samples")
            self.assertEqual(result["records"][0]["baseline"]["sample_count"],10)

    def test_unknown_identity_and_legacy_stay_unknown(self):
        data=works();data["schema_version"]="1.0"
        for r in data["records"]:
            r.pop("author_id");r.pop("collection_batch_id")
        result=decisions.calculate_baselines(data)
        self.assertEqual(result["schema_version"],2)
        self.assertIsNone(result["records"][0]["baseline"]["ratio"])
        self.assertIn("author_id",result["records"][0]["baseline"]["missing_fields"])

    def test_insufficient_and_zero_and_missing_target(self):
        self.assertEqual(decisions.calculate_baselines(works(10))["records"][0]["baseline"]["reason"],"insufficient_samples")
        data=works()
        for r in data["records"][1:]:r["like_count"]=0
        self.assertEqual(decisions.calculate_baselines(data)["records"][0]["baseline"]["reason"],"zero_baseline")
        data=works();data["records"][0]["like_count"]=None
        self.assertEqual(decisions.calculate_baselines(data)["records"][0]["baseline"]["reason"],"missing_target_metric")

    def test_views_require_groupwide_reliability_and_completeness(self):
        data=works()
        for i,r in enumerate(data["records"]):r.update(view_count=2000 if i==0 else 200,view_count_reliable=True)
        result=decisions.calculate_baselines(data)
        self.assertTrue(all(r["baseline"]["metric"]=="view_count" for r in result["records"]))
        data["records"][5]["view_count"]=None
        result=decisions.calculate_baselines(data)
        self.assertTrue(all(r["baseline"]["metric"]=="like_count" for r in result["records"]))

    def test_age_window_recent_30_and_missing_metrics(self):
        data=works(60)
        data["records"][0]["published_at"]=(AS_OF-timedelta(days=1)).isoformat()
        data["records"][1]["published_at"]=(AS_OF-timedelta(days=120)).isoformat()
        data["records"][2]["like_count"]=None
        result=decisions.calculate_baselines(data)
        target=result["records"][0]
        self.assertEqual(target["baseline"]["candidate_count"],30)
        self.assertEqual(target["baseline"]["sample_count"],29)
        self.assertNotIn("synthetic-1",target["baseline"]["sample_ids"])
        self.assertFalse(target["baseline_target_mature"])
        self.assertTrue(target["qualified"])

    def test_selection_uses_two_nearest_median_mature_works(self):
        data=decisions.calculate_baselines(works())
        selections=decisions.select_comparisons(data)["selections"]
        self.assertEqual(selections[0]["high_id"],"synthetic-0")
        self.assertEqual(len(selections[0]["ordinary_ids"]),2)
        self.assertNotIn("synthetic-0",selections[0]["ordinary_ids"])

class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.fixture=json.loads((ROOT/"tests/fixtures/synthetic_decisions.json").read_text())

    def test_split_merge_reorder_rewrite_add_delete_validate(self):
        result=decisions.validate_analysis(self.fixture["analysis"],self.fixture["sources"])
        self.assertEqual(result["citations_checked"],12)
        self.assertEqual({e["operation"] for e in self.fixture["analysis"]["evolution"]},
                         {"split","merge","reorder","rewrite","add","delete"})

    def test_quote_tampering_and_fake_time_fail(self):
        altered=deepcopy(self.fixture["analysis"])
        altered["evolution"][0]["to"][0]["quote"]="材料里没有这句话"
        with self.assertRaises(decisions.DecisionError):
            decisions.validate_analysis(altered,self.fixture["sources"])
        altered=deepcopy(self.fixture["analysis"])
        altered["evolution"][0]["from"][0].update(start_seconds=0,end_seconds=5)
        with self.assertRaisesRegex(decisions.DecisionError,"精确对齐"):
            decisions.validate_analysis(altered,self.fixture["sources"])

    def test_two_agent_drafts_keep_their_own_facts(self):
        first,second=self.fixture["cases"]
        for case in (first,second):
            self.assertEqual(decisions.validate_analysis(case["analysis"],self.fixture["sources"])["status"],"valid")
        a=first["analysis"]["draft_sections"][0];b=second["analysis"]["draft_sections"][0]
        self.assertNotEqual(a["text"],b["text"])
        self.assertEqual({c["source_id"] for c in a["own_facts"]},{"profile-a"})
        self.assertEqual({c["source_id"] for c in b["own_facts"]},{"profile-b"})
        self.assertIn("12 份",a["text"]);self.assertNotIn("12 份",b["text"])
        self.assertIn("两处",b["text"]);self.assertNotIn("两处",a["text"])

    def test_duplicate_source_alias_is_not_independent_evidence(self):
        sources=[{"source_id":k,"text":"同一条完整原文","platform":"douyin","content_id":"one"} for k in ["a","b"]]
        dims=[{"dimension":k,"observation":"材料不足","testable_change":"取得原文后再判断","alternative_explanations":["缺材料"],"status":"unknown"} for k in ["topic","hook","progression","proof","visual","comments"]]
        dims[0].update(status="observed",pattern_type="repeated",citations=[{"source_id":k,"quote":"同一条完整原文"} for k in ["a","b"]])
        with self.assertRaisesRegex(decisions.DecisionError,"独立内容"):
            decisions.validate_analysis({"comparisons":[{"dimensions":dims}]},sources)

class CommentTests(unittest.TestCase):
    def rows(self):
        return [{"platform":"douyin","content_id":"synthetic-v","comment_id":"q",
          "comment_text":"分错项目后怎么检查？","is_reply":False,"root_comment_id":"q","reply_count_reported":2,
          "reply_coverage":"partial","replies_fetched":1,"primary_category":"使用问题"},
          {"platform":"douyin","content_id":"synthetic-v","comment_id":"r","comment_text":"按原文链接检查。",
          "parent_comment_id":"q","root_comment_id":"q","is_reply":True,"is_content_author":True,"primary_category":"经验补充"},
          {"platform":"douyin","content_id":"synthetic-v","comment_id":"keyword","comment_text":"资料",
           "is_reply":False,"primary_category":"领取口令"}]
    def analysis(self):
        return {"questions":[{"id":"q1","question":"归类错误怎么检查","kind":"genuine_question",
          "members":[{"platform":"douyin","content_id":"synthetic-v","comment_id":"q"}],
          "thread_reviews":[{"platform":"douyin","content_id":"synthetic-v","comment_id":"q",
             "status":"answered","evidence_comment_ids":["r"],"reason":"回复给出了回到原文检查的方法"}],
          "video_addressed":"unknown"}]}

    def test_hierarchy_top_level_denominator_unknown_and_dedup(self):
        rows=self.rows();rows.append(deepcopy(rows[0]));rows.append({"comment_id":"legacy","content_id":"synthetic-v","text":"旧数据"})
        result=prepare.prepare_comment_records(rows)
        self.assertEqual(result["summary"]["denominator"],2)
        self.assertEqual(result["summary"]["reply_rows"],1)
        self.assertEqual(result["summary"]["hierarchy_unknown_rows"],1)
        self.assertEqual(result["summary"]["duplicates_removed"],1)
        self.assertEqual(result["records"][1]["parent_comment_id"],"q")

    def test_incomplete_replies_are_unknown_even_when_author_answers(self):
        prepared=prepare.prepare_comment_records(self.rows())
        result=decisions.aggregate_questions(prepared,self.analysis())
        self.assertEqual(result["questions"][0]["answer_counts"],{"unknown":1})
        self.assertEqual(result["questions"][0]["occurrences"],1)

    def test_complete_reply_can_be_answered_and_wrong_thread_cannot(self):
        rows=self.rows();rows[0].update(reply_count_reported=1,reply_coverage="complete")
        prepared=prepare.prepare_comment_records(rows)
        result=decisions.aggregate_questions(prepared,self.analysis())
        self.assertEqual(result["questions"][0]["answer_counts"],{"answered":1})
        bad=self.analysis();bad["questions"][0]["thread_reviews"][0]["evidence_comment_ids"]=["unrelated"]
        with self.assertRaises(decisions.DecisionError):decisions.aggregate_questions(prepared,bad)

    def test_claim_keyword_is_not_question_demand(self):
        analysis=self.analysis();analysis["questions"][0]["members"][0]["comment_id"]="keyword"
        self.assertEqual(decisions.aggregate_questions(prepare.prepare_comment_records(self.rows()),analysis)["questions"],[])

    def test_negative_video_claim_requires_full_review(self):
        data=prepare.prepare_comment_records(self.rows());analysis=self.analysis();q=analysis["questions"][0]
        q.update(video_addressed="not_addressed",video_citations=[{"source_id":"v","quote":"已经拿到的片段"}])
        sources=[{"source_id":"v","text":"已经拿到的片段","text_coverage":"partial"}]
        with self.assertRaisesRegex(decisions.DecisionError,"完整逐字稿"):
            decisions.aggregate_questions(data,analysis,sources)
        q["video_review"]={"full_transcript_reviewed":True,"reason":"按完整文本核对问题是否出现"}
        with self.assertRaisesRegex(decisions.DecisionError,"部分原文"):
            decisions.aggregate_questions(data,analysis,sources)
        sources[0]["text_coverage"]="full"
        self.assertEqual(decisions.aggregate_questions(data,analysis,sources)["questions"][0]["video_addressed"],"not_addressed")

class SavingTests(unittest.TestCase):
    def payload(self,state,text=None):
        return {"revision":state["revision"],"sections":[{"id":s["id"],"mine":text or s["mine"],"note":s.get("note","")} for s in state["sections"]]}

    def test_history_stale_analysis_and_sources_preserved(self):
        state=writing_state()
        updated=service.update_state(state,self.payload(state,"整理以后我还要核对原文。"))
        self.assertEqual(updated["revision"],2)
        self.assertEqual(updated["sources"],state["sources"])
        self.assertEqual(updated["sections"][0]["analysis_status"],"needs_review")
        self.assertEqual(updated["history"][0]["changes"][0]["before"]["mine"],state["sections"][0]["mine"])
        self.assertEqual(state["revision"],1)

    def test_conflict_and_locked_section_reject_overwrite(self):
        state=writing_state();payload=self.payload(state,"另一份改稿")
        payload["revision"]=0
        with self.assertRaises(service.Conflict):service.update_state(state,payload)
        payload["revision"]=1;state["sections"][0]["locked"]=True
        with self.assertRaisesRegex(decisions.DecisionError,"锁定"):service.update_state(state,payload)

    def test_http_save_readback_conflict_and_origin(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);state=writing_state();(root/"state.json").write_text(json.dumps(state))
            server=service.make_server(root,0);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            opener=build_opener(ProxyHandler({}));url=f"http://127.0.0.1:{server.server_port}"
            try:
                payload=json.dumps(self.payload(state,"已保存的新稿件")).encode()
                req=Request(url+"/api/save",data=payload,headers={"Content-Type":"application/json","Origin":url,"X-Workbench-Save":"1"})
                response=json.load(opener.open(req));self.assertEqual(response["state"]["revision"],2)
                self.assertEqual(json.load(opener.open(url+"/api/state"))["sections"][0]["mine"],"已保存的新稿件")
                self.assertIn("已保存的新稿件",(root/"writing.html").read_text())
                with self.assertRaises(HTTPError) as exc:opener.open(req)
                self.assertEqual(exc.exception.code,409)
                wrong=Request(url+"/api/save",data=payload,headers={"Content-Type":"application/json","Origin":"https://example.invalid","X-Workbench-Save":"1"})
                with self.assertRaises(HTTPError) as exc:opener.open(wrong)
                self.assertEqual(exc.exception.code,403)
            finally:server.shutdown();server.server_close();thread.join()

class TranscriptCapabilityTests(unittest.TestCase):
    def make(self,root,segments=None,**extra):
        (root/"corrected").mkdir();(root/"raw").mkdir()
        (root/"corrected/transcript_corrected.md").write_text("今天只讲一步。这里的词【待确认：项目名】不清楚。")
        records=segments if segments is not None else [{"text":"今天只讲一步。","start_seconds":0,"end_seconds":28}]
        (root/"raw/segments.jsonl").write_text("\n".join(json.dumps(s) for s in records))
        (root/"manifest.json").write_text(json.dumps({"status":"corrected_validated","duration_seconds":28,"segment_count":len(records),**extra}))

    def test_short_reviewed_text_with_local_uncertainty_is_usable(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);self.make(root);result=transcript.validate_transcript(root)
            self.assertTrue(result["capabilities"]["text_structure"])
            self.assertTrue(result["capabilities"]["block_timing"])
            self.assertFalse(result["capabilities"]["precise_timing"])
            self.assertEqual(len(result["uncertainties"]),1)
            with self.assertRaises(transcript.TranscriptNotReady):transcript.validate_transcript(root,"timing")

    def test_malformed_json_out_of_range_and_overlap_fail(self):
        for segments in [[{"text":"错","start_seconds":1,"end_seconds":40}],
                         [{"text":"甲","start_seconds":0,"end_seconds":20},{"text":"乙","start_seconds":15,"end_seconds":28}]]:
            with tempfile.TemporaryDirectory() as temp:
                root=Path(temp);self.make(root,segments)
                with self.assertRaises(transcript.TranscriptNotReady):transcript.validate_transcript(root)
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);self.make(root);(root/"raw/segments.jsonl").write_text("{")
            with self.assertRaises(transcript.TranscriptNotReady):transcript.validate_transcript(root)

    def test_coverage_gap_not_precise_but_verified_sentence_timing_is(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);self.make(root,[{"text":"缺口","start_seconds":5,"end_seconds":28}],time_precision="sentence",alignment_reviewed=True)
            self.assertFalse(transcript.validate_transcript(root)["capabilities"]["precise_timing"])
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);self.make(root,time_precision="sentence",alignment_reviewed=True)
            self.assertTrue(transcript.validate_transcript(root,"timing")["capabilities"]["precise_timing"])

if __name__=="__main__":
    unittest.main()
