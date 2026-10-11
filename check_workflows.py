"""上线前必跑：校验 .github/workflows/*.yml 能否被 GitHub 正确解析。

为什么需要它（血泪史）：
    2026-10 之前 update.yml 在 `gh issue create --body "..."` 里写了跨行中文，
    导致 YAML ScannerError。后果非常隐蔽且致命——GitHub 解析不了工作流时：
      · 压根不会注册 cron，所有 schedule 触发静默消失；
      · 连 push 触发也只是一个 0 秒就 failed 的空跑记录（jobs 数为 0），没有一句日志。
    于是整条数据管线悄悄停摆，data.json 停在 4 天前，用户只能感觉到「刷新频率太低」，
    而不是「管线挂了」。本地看 HTML/YAML 看不出异样，只有服务端解析失败。

所以推送 workflow 之前，务必先跑本脚本：
    python check_workflows.py

它做两件事：
  1. yaml.safe_load 能解析，且顶层有 name / jobs，每个 job 有 steps；
  2. 每个 step 的 run 脚体能通过 `bash -n` 语法检查（避免 again 被 shell 语法坑）。
任一项不通过就以非零码退出。
"""
from __future__ import annotations

import pathlib
import subprocess
import sys
import tempfile

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("需要 PyYAML：python -m pip install pyyaml")

ROOT = pathlib.Path(__file__).parent
FILES = sorted((ROOT / ".github" / "workflows").glob("*.y*ml"))


def check_bash(script: str) -> tuple[bool, str]:
    """用 bash -n 检查一段内联 shell 脚本的语法。"""
    with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False,
                                     encoding="utf-8") as fp:
        fp.write(script)
        path = fp.name
    try:
        r = subprocess.run(["bash", "-n", path], capture_output=True, text=True)
        return (r.returncode == 0), (r.stderr or "").strip()[:300]
    except FileNotFoundError:
        return True, "(skipped: 找不到 bash)"
    finally:
        pathlib.Path(path).unlink(missing_ok=True)


def main() -> int:
    if not FILES:
        print("没有找到 .github/workflows/*.yml")
        return 1

    fail = 0
    print(f"=== 校验 {len(FILES)} 个工作流文件 ===\n")
    for f in FILES:
        print(f"--- {f.relative_to(ROOT)} ---")
        try:
            d = yaml.safe_load(f.read_text(encoding="utf-8"))
        except Exception as e:
            fail += 1
            mark = getattr(e, "problem_mark", None)
            where = f" 第 {mark.line + 1} 行" if mark else ""
            print(f"  XX YAML 解析失败{where}: {type(e).__name__}: {e}")
            continue

        if not isinstance(d, dict) or "name" not in d:
            fail += 1
            print("  XX 顶层缺少 name（GitHub 会退回用文件路径命名，往往意味着解析异常）")
            continue
        print(f"  OK name = {d['name']!r}")

        on = d.get("on", d.get(True))
        trigs = list(on.keys()) if isinstance(on, dict) else on
        print(f"  OK 触发 = {trigs}")
        if isinstance(on, dict) and "schedule" in on:
            for item in on["schedule"]:
                print(f"     cron: {item.get('cron')}")
        if isinstance(on, dict) and "schedule" not in on:
            print("  -- 注意：没有 schedule，不会被定时触发")

        jobs = d.get("jobs") or {}
        if not jobs:
            fail += 1
            print("  XX 没有任何 job")
            continue
        for jn, job in jobs.items():
            steps = job.get("steps") or []
            if not steps:
                fail += 1
                print(f"  XX job {jn} 没有 steps")
                continue
            print(f"  OK job {jn}: {len(steps)} 步")
            for i, s in enumerate(steps, 1):
                label = s.get("name") or s.get("uses") or "(未命名)"
                if "uses" not in s and "run" not in s:
                    fail += 1
                    print(f"     XX step#{i} {label}: 既无 uses 也无 run")
                    continue
                run = s.get("run")
                if run:
                    ok, err = check_bash(run)
                    if not ok:
                        fail += 1
                        print(f"     XX step#{i} {label}: bash 语法错误\n        {err}")
                    else:
                        print(f"     OK step#{i} {label} (bash ok)")
                else:
                    print(f"     OK step#{i} {label}")
        print()

    if fail:
        print(f"=== FAIL：{fail} 处问题（修好再推送，否则服务端会静默停摆）===")
        return 1
    print("=== PASS：全部工作流可正常解析 ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
