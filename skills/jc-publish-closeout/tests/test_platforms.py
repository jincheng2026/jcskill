"""认链接、解析 TikHub 返回、认作品打分。不发请求。"""
import unittest

from support import DY_AWEME, XHS_NOTE, load_fixture

from closeout_kit import fetch as F
from closeout_kit import match as M
from closeout_kit import platforms as P
from closeout_kit.archive import parse_when


class LinkTest(unittest.TestCase):
    def test_抖音作品链接(self):
        t = P.parse_target("https://www.douyin.com/video/%s?previous_page=app" % DY_AWEME)
        self.assertEqual((t["platform"], t["id"]), ("抖音", DY_AWEME))

    def test_抖音分享文字里的短链接(self):
        t = P.parse_target("7.66 复制打开抖音，看看【某某的作品】AI 做会议纪要 https://v.douyin.com/AbCdEf12/ x@G.vs 09/30")
        self.assertEqual((t["platform"], t["short"], t["id"]), ("抖音", True, None))
        self.assertEqual(t["url"], "https://v.douyin.com/AbCdEf12/")

    def test_抖音网页精选页里的编号(self):
        t = P.parse_target("https://www.douyin.com/jingxuan?modal_id=%s" % DY_AWEME)
        self.assertEqual(t["id"], DY_AWEME)

    def test_小红书笔记(self):
        t = P.parse_target("https://www.xiaohongshu.com/explore/%s?xsec_token=abc" % XHS_NOTE)
        self.assertEqual((t["platform"], t["id"]), ("小红书", XHS_NOTE))
        self.assertEqual(P.parse_target(XHS_NOTE)["platform"], "小红书")

    def test_视频号认得出但抓不了(self):
        t = P.parse_target("https://channels.weixin.qq.com/web/pages/feed?eid=abc")
        self.assertEqual(t["platform"], "视频号")
        with self.assertRaises(Exception) as ctx:
            F.platform_or_fail(t)
        self.assertIn("视频号助手", str(ctx.exception))

    def test_主页链接认出账号(self):
        self.assertEqual(P.user_id_from_link("https://www.douyin.com/user/MS4wLjABAAAAfakeuser01?from=tab"), "MS4wLjABAAAAfakeuser01")
        self.assertEqual(P.user_id_from_link("https://www.xiaohongshu.com/user/profile/5f0000000000000000000001"), "5f0000000000000000000001")


class ParseTest(unittest.TestCase):
    def test_抖音作品数据(self):
        body = load_fixture("dy_detail.json")
        work = P.douyin_detail(body)
        self.assertEqual((work["likes"], work["collects"], work["comments"], work["shares"]), (5230, 2400, 260, 380))
        self.assertEqual(work["duration_seconds"], 52.4)
        self.assertIsNone(F._plays("抖音", body))  # 公开接口的 play_count 是 0：当成拿不到，不写 0

    def test_抖音播放数拿得到时照写(self):
        body = load_fixture("dy_detail.json")
        body["data"]["aweme_detail"]["statistics"]["play_count"] = 12345
        self.assertEqual(F._plays("抖音", body), 12345)

    def test_小红书笔记数据(self):
        work = P.xhs_note_detail(load_fixture("xhs_note_detail.json"))
        self.assertEqual((work["likes"], work["collects"], work["comments"], work["shares"]), (1200, 640, 88, 40))

    def test_抖音评论原话(self):
        rows, _cursor, more, total = P.douyin_comments(load_fixture("dy_comments_1.json"), DY_AWEME)
        self.assertEqual(rows[0]["text"], "方言能识别吗？我们开会都说四川话")
        self.assertTrue(more)
        self.assertEqual(total, 75)

    def test_删掉的作品说人话(self):
        with self.assertRaises(LookupError) as ctx:
            P.douyin_detail(load_fixture("dy_filtered.json"))
        self.assertIn("看不了", str(ctx.exception))


class MatchTest(unittest.TestCase):
    def setUp(self):
        self.works, _c, _m = P.douyin_works(load_fixture("dy_posts_1.json"))
        self.first = self.works[0]  # 虚构作品 1：让 AI 帮你改简历

    def test_标题和发布时间都对得上就认定(self):
        result = M.judge(self.works, "让 AI 帮你改简历", parse_when(self.first["published_at"]), self.first["duration_seconds"])
        self.assertEqual(result["verdict"], "认定")
        self.assertEqual(result["best"]["id"], self.first["id"])

    def test_同名的好几条又没有时间就拿不准(self):
        result = M.judge(self.works, "让 AI 帮你改简历", None, None)  # 第 1、9、17 条标题一样
        self.assertEqual(result["verdict"], "拿不准")
        self.assertEqual(len(result["candidates"]), 3)

    def test_一条都不像就没找到(self):
        result = M.judge(self.works, "量子计算机入门", parse_when("2025-01-01 10:00"), 300)
        self.assertEqual(result["verdict"], "没找到")


if __name__ == "__main__":
    unittest.main()
