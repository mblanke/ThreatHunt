from pathlib import Path

p = Path(r"d:\Projects\Dev\ThreatHunt\frontend\src\components\NetworkMap.tsx")
text = p.read_text(encoding="utf-8")

anchor = "  useEffect(() => { canvasSizeRef.current = canvasSize; }, [canvasSize]);\n"
insert = anchor + "\n  const sleep = (ms: number) => new Promise<void>(resolve => setTimeout(resolve, ms));\n"
if "const sleep = (ms: number)" not in text and anchor in text:
    text = text.replace(anchor, insert)

text = text.replace("await new Promise(r => setTimeout(r, delayMs + jitter));", "await sleep(delayMs + jitter);")

p.write_text(text, encoding="utf-8")
print("Patched sleep helper + polling awaits")