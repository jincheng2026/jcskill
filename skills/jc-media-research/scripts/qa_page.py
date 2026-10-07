#!/usr/bin/env python3
"""Screenshot checks for offline reports; visual inspection remains required."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_report_preview import find_browser, run_chromium

def shot(url, out, width, height, browser, require_ready=False):
    with tempfile.TemporaryDirectory(prefix="jc-page-qa-") as profile:
        command=[str(browser),"--headless=new","--no-sandbox","--disable-gpu","--hide-scrollbars",
            "--no-first-run","--no-default-browser-check","--run-all-compositor-stages-before-draw",
            "--virtual-time-budget=1800",f"--user-data-dir={profile}",f"--window-size={width},{height}",
            f"--screenshot={out}","--dump-dom",url]
        result=run_chromium(command)
        stdout=result.stdout
        if not Path(out).is_file() or Path(out).stat().st_size<1024:
            return False,"截图没有生成或浏览器超时"
        if require_ready and not re.search(r'<html\b[^>]*data-report-ready="true"',stdout):
            return False,"图表未进入就绪状态"
        if require_ready and re.search(r'<html\b[^>]*data-report-overflow="true"',stdout):
            return False,"页面实际横向溢出"
        return True,None

def analyze(png,label):
    im=Image.open(png).convert("RGB");w,h=im.size;px=im.load();bg=px[5,h-5]
    def blank(y):
        return all(sum(abs(px[x,y][i]-bg[i]) for i in range(3))<24 for x in range(20,w-20,16))
    bottom=next((y for y in range(h-1,0,-1) if not blank(y)),0)
    issues=[];notes=[]
    if h-bottom<24:issues.append(f"{label}：底部可能截断")
    if bottom<80:issues.append(f"{label}：页面近乎空白")
    if h-bottom>300:notes.append(f"{label}：裁去 {h-bottom}px 截图尾部空白")
    edge=sum(sum(abs(px[w-4,y][i]-bg[i]) for i in range(3))>40 for y in range(0,bottom,30))
    if edge>3:notes.append(f"{label}：右边缘有内容，需检查横向溢出")
    result=im.crop((0,0,w,min(h,bottom+40)))
    return result,issues,notes

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("html",type=Path)
    parser.add_argument("--height",type=int,default=6000)
    parser.add_argument("--width",type=int,default=1440)
    parser.add_argument("--outdir",type=Path,required=True)
    parser.add_argument("--browser")
    parser.add_argument("--mobile",action="store_true",help="另验收 500px 窄屏；更窄的手机布局用浏览器设备尺寸验证")
    args=parser.parse_args(argv)
    browser=find_browser(args.browser);source=args.html.resolve();out=args.outdir.resolve();out.mkdir(parents=True,exist_ok=True)
    text=source.read_text(encoding="utf-8");require_ready='id="chart-data"' in text
    results=[]
    with tempfile.TemporaryDirectory(prefix="jc-qa-theme-") as temp:
        dark=Path(temp)/"dark.html"
        dark.write_text(re.sub(r'(<html\b[^>]*)(>)',r'\1 data-theme="dark"\2',text,count=1),encoding="utf-8")
        modes=[("light",source,args.width),("dark",dark,args.width)]
        if args.mobile:modes.append(("mobile",source,500))
        for label,path,width in modes:
            png=out/f"{source.stem}_{label}.png";height=args.height
            for attempt in range(3):
                ok,error=shot(path.as_uri(),png,width,height,browser,require_ready)
                if not ok:results.append({"mode":label,"issues":[error]});break
                im,issues,notes=analyze(png,label)
                if any("底部可能截断" in x for x in issues) and height<20000:
                    height=min(20000,height*2);continue
                im.save(png)
                for i,y in enumerate(range(0,im.height,1400)):
                    im.crop((0,y,im.width,min(im.height,y+1400))).save(out/f"{source.stem}_{label}_sec{i}.png")
                results.append({"mode":label,"width":width,"height":im.height,"issues":issues,"notes":notes,
                    "screenshot":png.name,"chart_ready":require_ready,"visual_review":"required"})
                break
    passed=all(not r["issues"] for r in results)
    report={"status":"pass" if passed else "fail","checks":results,
            "limitations":["像素检查不能证明无文字重叠；需逐屏目检","命令行窄屏为 500px；390px 手机需在浏览器设备尺寸下核对"]}
    (out/"qa.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False))
    return 0 if passed else 1

if __name__=="__main__":
    raise SystemExit(main())
