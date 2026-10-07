# 给 AI 的安装说明：JC 内容创作系列

这份说明写给替用户安装的 AI（Codex、Claude Code 等）。用户把仓库链接交给你，说「照这个装好」，你照下面做。做完的样子：本系列 12 个 Skill（总入口 `jc` 和 11 个按阶段分工的 Skill）装进了这台电脑上的 Codex 和 Claude Code，工作文件夹建好了，你用 `jc` 带用户走完新手引导。

用户以后再发同样的话（想更新到新版本），你从第 0 步看装到哪一步了，做好的步骤跳过。

## 先看这几条

- 一步只做一件事，每步做完跑那一步的「检查」，看到「算成功」写的结果再往下走。检查不对，先看「不对时」；还解决不了，停下，把命令和完整输出告诉用户。
- 能自己查清的不问用户：用的是 Codex 还是 Claude Code、Skill 装在哪、缺什么工具，都自己查；缺什么就直接装，开装前用一句话告诉用户在装什么。
- 只有你做不了的事才请用户动手，而且做到那一步再说：系统弹窗点「安装」或「允许」、输入电脑开机密码、你的 AI 工具弹出请求点「允许」。一句话说清点哪里、输什么，用户回「好了」就接着做。
- 你的 AI 工具默认不让命令联网、写打开的文件夹以外的地方时（Codex 默认就是这样），安装中会请用户点几次「允许」（下载代码、装 Skill、建工作文件夹各一次左右）。第一次弹之前告诉用户：接下来会弹几次请求，都点允许就行。
- 安装时不问用户要任何 key，也不让用户把 key 发进对话。火山引擎和 TikHub 的 key 等第一次真用到时，对应的 Skill 会告诉用户去哪申请、怎么放进钥匙串。
- 下载代码只用 `git clone`，不用网页上的 Download ZIP（压缩包没有 git 记录，以后没法更新）。
- 下面写的 `~/jcskill` 是代码文件夹的默认位置；第 0 步发现装在别处，后面的路径都换成实际的。`<仓库地址>` 用用户给的链接；没给就用 https://github.com/jincheng2026/jcskill 。

## 第 0 步：看看装到哪一步了

```bash
git -C ~/jcskill remote get-url origin 2>/dev/null || echo 没有
```

- 输出「没有」，并且 `~/jcskill` 不存在：还没装，从第 1 步开始。
- 输出的地址是这个仓库（用户给的链接或上面的正式地址，结尾多 `.git`、用户名写成旧名 `luozitianyuan` 都算）：装过了，先更新：

  ```bash
  git -C ~/jcskill pull --ff-only
  ```

  打印 `Already up to date.` 或拉到新提交都算成功，跳到第 3 步（会认出装过的 Skill，只补新的）。报本地有改动、合不上：用户改过这里的文件，不要丢掉他的改动，停下，把报错原样告诉用户。
- `~/jcskill` 存在但不是这个仓库：不动它，代码换个地方装：后面的 `~/jcskill` 都换成 `~/jcskill-app`（也被占了就加 2、3），从第 1 步开始。

## 第 1 步：确认有 Git 和 Python 3

```bash
git --version && python3 --version
```

- 算成功：输出 `git version 2.` 开头一行，和 `Python 3.` 开头一行（3.10 或更新）。
- 不对时：macOS 弹出「需要安装命令行开发者工具」的窗口，请用户点「安装」，装完再检查；没弹窗，你运行 `xcode-select --install`，弹窗时请用户点「安装」。Python 比 3.10 旧：有 Homebrew（`brew --version` 有输出）就 `brew install python`，没有就先照 https://brew.sh 的一行命令装 Homebrew（中途要输一次开机密码：你的终端里输不了的话，把命令给用户，请他在「终端」里运行，装完告诉你）。

## 第 2 步：下载代码

```bash
git clone <仓库地址> ~/jcskill
git -C ~/jcskill log --oneline -1
```

- 算成功：第二条输出一行，开头是一串字母和数字。
- 不对时：提示 `already exists and is not an empty directory`：回第 0 步。连不上 GitHub：问用户平时上网是不是要开代理，开着代理再试。

## 第 3 步：把 Skill 装进 AI 工具

装哪几个：本系列 12 个 Skill。

```text
jc jc-media-research jc-benchmark-intake jc-video-analysis jc-jiaocheng-video jc-zhuanxie
jc-gongzuotai-write jc-jianjie jc-koubo-shuping jc-publish-closeout jc-media-review jc-skill-writer
```

用户说了要「整套装」或「通用的也要」，仓库 `skills/` 里另外 10 个通用 Skill（jc-clarifier、jc-ask-anything、jc-plan、jc-daily-planning、jc-learn-anything、jc-write、jc-handoff、jc-source-of-truth、jc-wechat-publish、jc-zhuagongzhonghao）也照同样办法装；没说就不装。

装到哪，自己查：

- 你自己是哪个 AI 工具，就装进哪个；这台电脑上另一个也在，也一起装。有 `~/.codex` 文件夹（或 `command -v codex` 有输出）就是装了 Codex；有 `~/.claude` 文件夹（或 `command -v claude` 有输出）就是装了 Claude Code。
- Codex 的 Skill 放在 `~/.codex/skills/`（设了环境变量 `CODEX_HOME` 的，放在 `$CODEX_HOME/skills/`）；Claude Code 的放在 `~/.claude/skills/`。

用软链装（Skill 文件夹直接指着仓库里的那份，以后 `git pull` 更新了 Skill 也跟着新）。下面以 Codex 为例，Claude Code 把 `$DEST` 换成 `~/.claude/skills`：

```bash
DEST="${CODEX_HOME:-$HOME/.codex}/skills"
mkdir -p "$DEST"
for s in jc jc-media-research jc-benchmark-intake jc-video-analysis jc-jiaocheng-video jc-zhuanxie jc-gongzuotai-write jc-jianjie jc-koubo-shuping jc-publish-closeout jc-media-review jc-skill-writer; do
  if [ -e "$DEST/$s" ] || [ -L "$DEST/$s" ]; then
    echo "已存在：$s -> $(readlink "$DEST/$s" || echo 普通文件夹)"
  else
    ln -sn "$HOME/jcskill/skills/$s" "$DEST/$s" && echo "装好：$s"
  fi
done
```

`ln` 的 `-n` 不能省。检查：

```bash
for s in jc jc-zhuanxie jc-publish-closeout; do sed -n 2p "$DEST/$s/SKILL.md"; done
```

- 算成功：打印三行 `name: jc`、`name: jc-zhuanxie`、`name: jc-publish-closeout`。
- 「已存在」的那些，看它指向哪：
  - 指向 `~/jcskill/skills/` 里的同名文件夹：装过了，不用管。
  - 是普通文件夹，里面 `SKILL.md` 第 2 行是同一个名字：以前复制装的旧版本，或者是用户自己的同名 Skill。**不要删也不要覆盖**，把这几个名字列给用户，问他：换成仓库里的（你把旧的挪进废纸篓 `~/.Trash/`，再装）还是保留他自己的。等他回答再动。
  - 别的东西：不动，告诉用户这个位置被占了、占着的是什么。
- 不能用软链时（比如同步软件不认软链）：`ln -sn` 换成 `cp -R "$HOME/jcskill/skills/$s" "$DEST/"`。复制的不会跟着更新，以后每次更新完都要再复制一次。

## 第 4 步：确认有 ffmpeg

转文字、对标入库、拆视频都要用 ffmpeg 处理音视频。

```bash
ffmpeg -version | head -1 && ffprobe -version | head -1
```

- 算成功：两行，分别以 `ffmpeg version`、`ffprobe version` 开头。
- 不对时：有 Homebrew 就 `brew install ffmpeg`；没有 Homebrew，照第 1 步装好 Homebrew 再装。

Node.js、Remotion（竖屏口播剪辑用）和创作工作台（创作页、封面用）这一步不装：第一次用 jc-koubo-shuping、jc-gongzuotai-write 时，那两个 Skill 会自己装。

## 第 5 步：体检、建工作文件夹

```bash
python3 "$DEST/jc/scripts/doctor.py"
python3 "$DEST/jc/scripts/init_workfolder.py"
```

- 算成功：体检第一行是「Skill：本系列 12 个都装好了（总入口 jc 加 11 个）」；第二条打印「工作文件夹：…」。工作文件夹默认在 `~/Documents/jincheng-workbench/`，和开源的创作工作台用的是同一个；已经装过工作台的，会认出它原有的工作文件夹，只补缺的，不覆盖任何文件。
- 不对时：缺 Skill 回第 3 步；工作文件夹「写不了」，多半是你的 AI 工具只许写打开的文件夹，先用一句话告诉用户要点什么，再申请写权限；macOS 弹窗问能不能访问「文稿」文件夹，请用户点「好」。

## 第 6 步：告诉用户结果，开始新手引导

新开的对话最稳：Skill 刚装好时，当前对话可能还看不到它们。你能直接读到 `$DEST/jc/SKILL.md` 的话，就在这个对话里照它的「新手引导」做；读不到，告诉用户新开一个对话，发「用 jc 带我走一遍新手引导」。

告诉用户的话只说结果，几句就够：

> JC 内容创作系列装好了（{Codex / Claude Code / 两个都装了}），一共 12 个 Skill。你的工作文件夹在 `{路径}`，选题、草稿、素材、发布档案都放这里。
> 用到火山引擎（转文字）和 TikHub（抓数据）时，我会提醒你去哪申请 key、怎么放进钥匙串，现在不用管。
> 以后想更新，把装的那句话再发一次就行。

然后接着做新手引导。
