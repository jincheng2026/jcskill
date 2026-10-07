"""到点没抓的怎么算；没有密钥时说人话、不报 Python 异常；读密钥的顺序。"""
import json
import os
import subprocess
import unittest

from support import DY_AWEME, FAKE_KEY, TEST_SERVICE, FakeTikHub, TempWork, dy_detail, run_cli

from closeout_kit import tikhub as T

DETAIL = "/api/v1/douyin/app/v3/fetch_one_video"


class DueTest(unittest.TestCase):
    def setUp(self):
        self.w = TempWork()
        self.fake = FakeTikHub({DETAIL: lambda p: (200, dy_detail(), 0)})
        self.env = self.w.env(TIKHUB_API_KEY=FAKE_KEY, TIKHUB_BASE_URL=self.fake.base)
        code, out = run_cli(["create", "--workfolder", self.w.work, "--title", "让 AI 帮你改简历", "--published", "2026-10-07 20:00",
                             "--now", "2026-10-07 21:00"], self.env)
        self.assertEqual(code, 0, out)
        self.archive = self.w.archives()[0]
        code, out = run_cli(["link", "--archive", self.archive, "--url", "https://www.douyin.com/video/%s" % DY_AWEME,
                             "--published", "2026-10-07 20:00", "--duration", "52", "--now", "2026-10-07 21:00"], self.env)
        self.assertEqual(code, 0, out)

    def tearDown(self):
        self.fake.close()
        self.w.cleanup()

    def due(self, now):
        code, out = run_cli(["due", "--workfolder", self.w.work, "--now", now, "--json"], self.env)
        self.assertEqual(code, 0, out)
        return json.loads(out)

    def test_没到点时只给下一个到点(self):
        result = self.due("2026-10-08 07:59")
        self.assertEqual(result["due"], [])
        self.assertEqual((result["next"]["platform"], result["next"]["point"], result["next"]["target_at"]), ("抖音", "12h", "2026-10-08 08:00"))
        self.assertEqual([w["platforms"] for w in result["waiting"]], [["小红书", "视频号"]])

    def test_过了到点就列出来_写清过了多久(self):
        result = self.due("2026-10-08 10:30")
        self.assertEqual([(d["platform"], d["point"], d["late"]) for d in result["due"]], [("抖音", "12h", "2 小时 30 分钟")])

    def test_抓过的不再列_七天到了再列(self):
        run_cli(["record", "--archive", self.archive, "--point", "12h", "--now", "2026-10-08 08:10"], self.env)
        self.assertEqual(self.due("2026-10-10 00:00")["due"], [])
        self.assertEqual([d["point"] for d in self.due("2026-10-15 09:00")["due"]], ["7d"])

    def test_发布三天以后不再提醒认作品(self):
        self.assertEqual(self.due("2026-10-11 21:00")["waiting"], [])

    def test_七天齐了提醒复盘(self):
        for p in ("小红书", "视频号"):
            run_cli(["link", "--archive", self.archive, "--platform", p, "--status", "不发"], self.env)
        run_cli(["record", "--archive", self.archive, "--point", "12h", "--now", "2026-10-08 08:10"], self.env)
        run_cli(["record", "--archive", self.archive, "--point", "7d", "--now", "2026-10-14 20:10"], self.env)
        result = self.due("2026-10-14 21:00")
        self.assertEqual(len(result["review"]), 1)
        code, out = run_cli(["due", "--workfolder", self.w.work, "--now", "2026-10-14 21:00"], self.env)
        self.assertIn("还没复盘", out)
        self.assertLessEqual(len(out.strip().splitlines()), 3)  # 输出简短

    def test_文字输出简短(self):
        code, out = run_cli(["due", "--workfolder", self.w.work, "--now", "2026-10-08 10:30"], self.env)
        self.assertEqual(code, 0, out)
        self.assertIn("到点还没抓的数据（1 项）", out)
        self.assertIn("已经过了 2 小时 30 分钟", out)
        self.assertLessEqual(len(out.strip().splitlines()), 6)

    def test_没有档案(self):
        w = TempWork()
        try:
            code, out = run_cli(["due", "--workfolder", w.work], w.env())
            self.assertEqual((code, out.strip()), (0, "还没有已发布的档案。"))
        finally:
            w.cleanup()


class NoKeyTest(unittest.TestCase):
    def setUp(self):
        self.w = TempWork()
        self.env = self.w.env(TIKHUB_API_KEY="")

    def tearDown(self):
        self.w.cleanup()

    def test_check_没有密钥说人话(self):
        code, out = run_cli(["check"], self.env)
        self.assertEqual(code, 2, out)
        self.assertIn("还没读到 TikHub 的密钥", out)
        self.assertIn("security add-generic-password -a tikhub -s tikhub-api -U -w", out)
        self.assertIn("数据来源", out)
        self.assertNotIn("Traceback", out)

    def test_fetch_没有密钥说人话(self):
        code, out = run_cli(["fetch", "https://www.douyin.com/video/%s" % DY_AWEME], self.env)
        self.assertEqual(code, 2, out)
        self.assertIn("还没读到 TikHub 的密钥", out)
        self.assertNotIn("Traceback", out)

    def test_record_没有密钥说人话_不写档案(self):
        run_cli(["create", "--workfolder", self.w.work, "--title", "测试", "--published", "2026-10-07 20:00"], self.env)
        archive = self.w.archives()[0]
        run_cli(["link", "--archive", archive, "--url", "https://www.douyin.com/video/%s" % DY_AWEME, "--published", "2026-10-07 20:00",
                 "--duration", "52"], self.env)
        code, out = run_cli(["record", "--archive", archive, "--point", "12h", "--now", "2026-10-08 09:00"], self.env)
        self.assertEqual(code, 2, out)
        self.assertIn("还没读到 TikHub 的密钥", out)
        with open(os.path.join(archive, "数据.jsonl"), encoding="utf-8") as f:
            self.assertEqual(f.read().strip(), "")


class FakeRun(object):
    def __init__(self, code=0, out="keychain-key-value\n"):
        self.code, self.out, self.calls = code, out, []

    def __call__(self, command, **kwargs):
        self.calls.append(command)
        return subprocess.CompletedProcess(command, self.code, self.out, "")


class KeyOrderTest(unittest.TestCase):
    def test_先读环境变量(self):
        run = FakeRun()
        self.assertEqual(T.read_key({"TIKHUB_API_KEY": " env-key ", "JC_TIKHUB_KEYCHAIN_SERVICE": TEST_SERVICE}, run), ("env-key", "环境变量 TIKHUB_API_KEY"))
        self.assertEqual(run.calls, [])

    def test_再读钥匙串_测试用测试专用名字(self):
        run = FakeRun()
        self.assertEqual(T.read_key({"JC_TIKHUB_KEYCHAIN_SERVICE": TEST_SERVICE}, run), ("keychain-key-value", "钥匙串"))
        self.assertEqual(run.calls[0], ["/usr/bin/security", "find-generic-password", "-s", TEST_SERVICE, "-a", "tikhub", "-w"])

    def test_默认条目和创作工作台一样(self):
        self.assertEqual(T.keychain_service({}), "tikhub-api")


if __name__ == "__main__":
    unittest.main()
