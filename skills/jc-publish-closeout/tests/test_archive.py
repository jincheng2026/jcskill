"""建档、记作品、到点抓数、总览、复盘、选题状态。TikHub 全部换成本机的假服务。"""
import json
import os
import unittest

from support import DY_AWEME, DY_HOME, FAKE_KEY, FakeTikHub, TempWork, dy_detail, load_fixture, ok, run_cli

DETAIL = "/api/v1/douyin/app/v3/fetch_one_video"
XHS_DETAIL = "/api/v1/xiaohongshu/app_v2/get_image_note_detail"
POSTS = "/api/v1/douyin/app/v3/fetch_user_post_videos"
TITLE = "让 AI 帮你改简历"
PUBLISHED = "2026-10-07 20:00"


class Base(unittest.TestCase):
    def setUp(self):
        self.w = TempWork()
        self.likes = [5230]
        self.fake = FakeTikHub({DETAIL: lambda p: (200, dy_detail(likes=self.likes[0]), 0),
                                XHS_DETAIL: ok(load_fixture("xhs_note_detail.json")),
                                POSTS: ok(load_fixture("dy_posts_1.json"))})
        self.env = self.w.env(TIKHUB_API_KEY=FAKE_KEY, TIKHUB_BASE_URL=self.fake.base)

    def tearDown(self):
        self.fake.close()
        self.w.cleanup()

    def cli(self, *args, **kw):
        code, out = run_cli(list(args), kw.get("env") or self.env)
        return code, out

    def create(self, *extra):
        code, out = self.cli("create", "--workfolder", self.w.work, "--title", TITLE, "--published", PUBLISHED,
                             "--id", "T001", "--now", "2026-10-07 21:00", *extra)
        self.assertEqual(code, 0, out)
        return self.w.archives()[0]

    def link_douyin(self, archive):
        code, out = self.cli("link", "--archive", archive, "--url", "https://www.douyin.com/video/%s" % DY_AWEME,
                             "--published", PUBLISHED, "--duration", "52.4", "--now", "2026-10-07 21:00")
        self.assertEqual(code, 0, out)

    def records(self, archive):
        with open(os.path.join(archive, "数据.jsonl"), encoding="utf-8") as f:
            return [json.loads(l) for l in f if l.strip()]


class CreateTest(Base):
    def test_建档写好内容和总览(self):
        cover = self.w.write("封面原图.png", "fake-png")
        transcript = self.w.write("逐字稿.txt", "0:00 你改简历是不是总被刷？")
        archive = self.create("--cover", cover, "--transcript", transcript, "--intro", "三步改好简历", "--video", cover)
        self.assertEqual(os.path.basename(archive), "2026-10-07-让 AI 帮你改简历")
        text = self.w.read("已发布", os.path.basename(archive), "内容.md")
        for piece in ("- **T 编号**：T001", "- **发布时间**：2026-10-07 20:00", "- **简介**：三步改好简历", "[封面.png](封面.png)",
                      "（没复制进档案）", "0:00 你改简历是不是总被刷？", "## 复盘", "| 抖音 | 预计发布 |"):
            self.assertIn(piece, text)
        self.assertTrue(os.path.isfile(cover))  # 原件没动
        self.assertTrue(os.path.isfile(os.path.join(archive, "封面.png")))
        self.assertEqual(os.listdir(archive).count("数据.jsonl"), 1)
        overview = self.w.read("已发布", "00_已发布总览.md")
        self.assertIn("| 2026-10-07 | 让 AI 帮你改简历 | T001 | 还没认出 | 还没认出 | 还没认出 | 还没复盘 |", overview)

    def test_重复调用不重复建档(self):
        self.create()
        code, out = self.cli("create", "--workfolder", self.w.work, "--title", TITLE, "--published", PUBLISHED, "--id", "T001",
                             "--intro", "新简介", "--now", "2026-10-07 22:00")
        self.assertEqual(code, 0, out)
        self.assertIn("没重复建", out)
        self.assertEqual(len(self.w.archives()), 1)
        overview = self.w.read("已发布", "00_已发布总览.md")
        self.assertEqual(overview.count("让 AI 帮你改简历 | T001"), 1)

    def test_选题总览改成已发布_卡挪到已做(self):
        self.create()
        overview = self.w.read("选题库", "00_选题总览.md")
        self.assertIn("| T001 | 让 AI 帮你改简历 | 自己的想法 | 已发布 | 2026-10-07 |  |", overview)
        self.assertIn("| T002 | 另一条 | 自己的想法 | 待写 |  |  |", overview)  # 别的行不动
        self.assertEqual(overview.count("**待做**"), 1)
        card = self.w.path("选题库", "口播", "已做", "T001_让AI帮你改简历.md")
        self.assertTrue(os.path.isfile(card))
        self.assertFalse(os.path.exists(self.w.path("选题库", "口播", "待做", "T001_让AI帮你改简历.md")))
        with open(card, encoding="utf-8") as f:
            text = f.read()
        self.assertIn("- **状态**：已发布", text)
        self.assertIn("- **发布日期**：2026-10-07\n- **效果**：", text)

    def test_没有选题总览也能建档(self):
        os.remove(self.w.path("选题库", "00_选题总览.md"))
        self.create()
        self.assertEqual(len(self.w.archives()), 1)


class RecordTest(Base):
    def test_十二小时到点抓数_追加不覆盖(self):
        archive = self.create()
        self.link_douyin(archive)
        code, out = self.cli("record", "--archive", archive, "--point", "12h", "--now", "2026-10-08 08:20")
        self.assertEqual(code, 0, out)
        self.assertIn("晚 20 分钟", out)
        self.likes[0] = 9000
        code, out = self.cli("record", "--archive", archive, "--point", "7d", "--now", "2026-10-14 20:05")
        self.assertEqual(code, 0, out)
        rows = self.records(archive)
        self.assertEqual([(r["point"], r["likes"]) for r in rows], [("12h", 5230), ("7d", 9000)])
        self.assertEqual(rows[0]["target_at"], "2026-10-08 08:00")
        self.assertEqual(rows[0]["collected_at"], "2026-10-08 08:20")
        self.assertEqual(rows[0]["delay_minutes"], 20)
        self.assertIsNone(rows[0]["plays"])  # 拿不到写空，不写 0
        text = self.w.read("已发布", os.path.basename(archive), "内容.md")
        self.assertIn("| 抖音 | 12 小时 | 2026-10-08 08:00 | 2026-10-08 08:20 | 晚 20 分钟 | — | 5230 | 2400 | 260 | 380 | TikHub |", text)
        self.assertIn("| 抖音 | 7 天 | 2026-10-14 20:00 | 2026-10-14 20:05 | 晚 5 分钟 | — | 9000 |", text)
        overview = self.w.read("已发布", "00_已发布总览.md")
        self.assertIn("| 9000／2400 |", overview)
        self.assertNotIn(FAKE_KEY, self.w.all_text())  # 密钥不落盘
        self.assertTrue(all(r["auth"] == "Bearer " + FAKE_KEY for r in self.fake.paid()))

    def test_已经记过的不重复记(self):
        archive = self.create()
        self.link_douyin(archive)
        self.cli("record", "--archive", archive, "--point", "12h", "--now", "2026-10-08 08:20")
        code, out = self.cli("record", "--archive", archive, "--point", "12h", "--now", "2026-10-08 09:00")
        self.assertEqual(code, 0, out)
        self.assertIn("已经记过了", out)
        self.assertEqual(len(self.records(archive)), 1)
        self.assertEqual(len([r for r in self.fake.paid() if r["path"] == DETAIL]), 1)

    def test_晚采照写晚了多久(self):
        archive = self.create()
        self.link_douyin(archive)
        code, out = self.cli("record", "--archive", archive, "--point", "12h", "--now", "2026-10-09 11:30")
        self.assertEqual(code, 0, out)
        row = self.records(archive)[0]
        self.assertEqual(row["delay"], "晚 1 天 3 小时，偏晚")
        self.assertEqual(row["target_at"], "2026-10-08 08:00")  # 目标时间照旧，不改成采集时间
        text = self.w.read("已发布", os.path.basename(archive), "内容.md")
        self.assertIn("| 2026-10-08 08:00 | 2026-10-09 11:30 | 晚 1 天 3 小时，偏晚 |", text)

    def test_没到点不抓(self):
        archive = self.create()
        self.link_douyin(archive)
        code, out = self.cli("record", "--archive", archive, "--point", "12h", "--now", "2026-10-08 07:00")
        self.assertIn("还没到", out)
        self.assertEqual(self.records(archive), [])
        self.assertEqual(self.fake.paid(), [])

    def test_视频号手动记数_写明来源(self):
        archive = self.create()
        code, out = self.cli("link", "--archive", archive, "--platform", "视频号", "--published", "2026-10-07 20:10", "--now", "2026-10-07 21:00")
        self.assertEqual(code, 0, out)
        code, out = self.cli("record", "--archive", archive, "--point", "12h", "--now", "2026-10-08 09:00")
        self.assertEqual(code, 2, out)  # 视频号 TikHub 抓不了，说清楚要截图
        self.assertIn("视频号助手", out)
        code, out = self.cli("record", "--archive", archive, "--point", "12h", "--platform", "视频号", "--likes", "12", "--collects", "3",
                             "--source", "视频号助手截图", "--collected-at", "2026-10-08 08:40", "--now", "2026-10-08 09:00")
        self.assertEqual(code, 0, out)
        row = self.records(archive)[0]
        self.assertEqual((row["likes"], row["collects"], row["comments"], row["source"]), (12, 3, None, "视频号助手截图"))
        self.assertEqual(row["collected_at"], "2026-10-08 08:40")

    def test_一个平台失败不拖垮别的平台(self):
        archive = self.create()
        self.link_douyin(archive)
        self.cli("link", "--archive", archive, "--platform", "视频号", "--published", PUBLISHED, "--now", "2026-10-07 21:00")
        code, out = self.cli("record", "--archive", archive, "--point", "12h", "--now", "2026-10-08 08:30")
        self.assertEqual(code, 0, out)
        self.assertEqual([r["platform"] for r in self.records(archive)], ["抖音"])
        self.assertIn("视频号助手", out)

    def test_小红书要先问用户(self):
        archive = self.create()
        code, out = self.cli("link", "--archive", archive, "--url", "https://www.xiaohongshu.com/explore/660000000000000000000001",
                             "--published", PUBLISHED, "--duration", "52", "--now", "2026-10-07 21:00")
        self.assertEqual(code, 0, out)
        code, out = self.cli("record", "--archive", archive, "--point", "12h", "--now", "2026-10-08 08:30")
        self.assertEqual(code, 3, out)
        self.assertIn("需要用户同意", out)
        self.assertEqual(self.fake.paid(), [])
        code, out = self.cli("record", "--archive", archive, "--point", "12h", "--agreed-budget", "0.01", "--now", "2026-10-08 08:30")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.records(archive)[0]["likes"], 1200)

    def test_记没采到以后不再提醒(self):
        archive = self.create()
        self.link_douyin(archive)
        code, out = self.cli("record", "--archive", archive, "--point", "12h", "--platform", "抖音", "--missed", "那天 TikHub 余额不够",
                             "--now", "2026-10-09 10:00")
        self.assertEqual(code, 0, out)
        code, out = self.cli("due", "--workfolder", self.w.work, "--now", "2026-10-09 10:00")
        self.assertNotIn("抖音 12 小时", out)
        text = self.w.read("已发布", os.path.basename(archive), "内容.md")
        self.assertIn("没采到：那天 TikHub 余额不够", text)

    def test_link_不给发布时间就从平台读(self):
        archive = self.create()
        code, out = self.cli("link", "--archive", archive, "--url", "https://www.douyin.com/video/%s" % DY_AWEME, "--now", "2026-10-07 21:00")
        self.assertEqual(code, 0, out)
        text = self.w.read("已发布", os.path.basename(archive), "内容.md")
        self.assertIn("| 抖音 | 已找到 | https://www.douyin.com/video/%s |" % DY_AWEME, text)
        self.assertIn("52.4 秒", text)


class FindTest(Base):
    def test_没记主页就请用户贴一次(self):
        archive = self.create()
        code, out = self.cli("find", "--archive", archive, "--platform", "抖音")
        self.assertEqual(code, 2, out)
        self.assertIn("主页链接", out)
        self.assertEqual(self.fake.paid(), [])

    def test_从主页认出作品并记进档案(self):
        code, out = self.cli("account", "--workfolder", self.w.work, "--platform", "抖音", "--url", DY_HOME)
        self.assertEqual(code, 0, out)
        works = load_fixture("dy_posts_1.json")["data"]["aweme_list"]
        from closeout_kit.text import unix_to_text
        first_time = unix_to_text(works[0]["create_time"])
        code, out = self.cli("create", "--workfolder", self.w.work, "--title", TITLE, "--published", first_time, "--id", "T001",
                             "--now", first_time)
        self.assertEqual(code, 0, out)
        archive = self.w.archives()[0]
        code, out = self.cli("find", "--archive", archive, "--platform", "抖音", "--apply", "--now", first_time)
        self.assertEqual(code, 0, out)
        self.assertIn("认定是第 1 条", out)
        text = self.w.read("已发布", os.path.basename(archive), "内容.md")
        self.assertIn("| 抖音 | 已找到 | https://www.douyin.com/video/7400000000000000101 |", text)
        posts = [r for r in self.fake.paid() if r["path"] == POSTS]
        self.assertEqual(posts[0]["params"]["sec_user_id"], "MS4wLjABAAAAfakeuser01")


class ReviewTest(Base):
    def test_复盘写进内容_旧的先备份_总览标已复盘(self):
        archive = self.create()
        review = self.w.write("复盘.md", "## 复盘\n\n#### 已确认的事实\n\n- 抖音 7 天点赞 9000。\n")
        code, out = self.cli("review", "--archive", archive, "--file", review, "--now", "2026-10-15 10:00")
        self.assertEqual(code, 0, out)
        text = self.w.read("已发布", os.path.basename(archive), "内容.md")
        self.assertIn("> 复盘于 2026-10-15", text)
        self.assertIn("#### 已确认的事实", text)
        self.assertNotIn("（还没复盘）", text)
        self.assertEqual(text.count("\n## 复盘"), 1)
        history = os.listdir(os.path.join(archive, ".history"))
        self.assertEqual(len(history), 1)
        with open(os.path.join(archive, ".history", history[0]), encoding="utf-8") as f:
            self.assertIn("（还没复盘）", f.read())
        self.assertIn("| 已复盘 2026-10-15 |", self.w.read("已发布", "00_已发布总览.md"))


if __name__ == "__main__":
    unittest.main()
