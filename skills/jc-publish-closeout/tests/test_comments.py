"""抓评论原话（复盘用）：原话照抄、不超过条数、花钱前算好。"""
import json
import unittest

from support import DY_AWEME, FAKE_KEY, FakeTikHub, TempWork, dy_detail, load_fixture, ok, run_cli

DETAIL = "/api/v1/douyin/app/v3/fetch_one_video"
COMMENTS = "/api/v1/douyin/app/v3/fetch_video_comments"


class CommentsTest(unittest.TestCase):
    def setUp(self):
        self.w = TempWork()
        pages = {"0": load_fixture("dy_comments_1.json"), "20": load_fixture("dy_comments_2.json")}
        self.fake = FakeTikHub({DETAIL: lambda p: (200, dy_detail(), 0),
                                COMMENTS: lambda p: (200, pages.get(p.get("cursor"), load_fixture("dy_comments_empty.json")), 0)})
        self.env = self.w.env(TIKHUB_API_KEY=FAKE_KEY, TIKHUB_BASE_URL=self.fake.base)

    def tearDown(self):
        self.fake.close()
        self.w.cleanup()

    def test_原话照抄_存成文件(self):
        save = self.w.path("评论.json")
        code, out = run_cli(["comments", "https://www.douyin.com/video/%s" % DY_AWEME, "--max", "5", "--save", save], self.env)
        self.assertEqual(code, 0, out)
        self.assertIn("「方言能识别吗？我们开会都说四川话」", out)
        with open(save, encoding="utf-8") as f:
            data = json.load(f)
        top = [c for c in data["comments"] if c["level"] == "一级"]
        self.assertEqual(len(top), 5)
        self.assertNotIn("_user", data["comments"][0])  # 不带评论人的账号
        self.assertEqual(len([r for r in self.fake.paid() if r["path"] == COMMENTS]), 1)

    def test_超过200条要先问(self):
        code, out = run_cli(["comments", "https://www.douyin.com/video/%s" % DY_AWEME, "--max", "300"], self.env)
        self.assertEqual(code, 3, out)
        self.assertIn("需要用户同意", out)
        self.assertEqual(self.fake.paid(), [])

    def test_没有评论就说暂无评论(self):
        self.fake.routes[COMMENTS] = ok(load_fixture("dy_comments_empty.json"))
        code, out = run_cli(["comments", "https://www.douyin.com/video/%s" % DY_AWEME], self.env)
        self.assertEqual(code, 0, out)
        self.assertIn("暂无评论", out)


if __name__ == "__main__":
    unittest.main()
