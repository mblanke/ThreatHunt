from pathlib import Path
import re

p = Path(r"d:\Projects\Dev\ThreatHunt\frontend\src\components\NetworkMap.tsx")
text = p.read_text(encoding="utf-8")
pattern = re.compile(r"const waitUntilReady = async \(\): Promise<boolean> => \{[\s\S]*?\n\s*\};", re.M)
replacement = '''const waitUntilReady = async (): Promise<boolean> => {
      // Poll inventory-status with exponential backoff until 'ready' (or cancelled)
      setProgress('Host inventory is being prepared in the background');
      setLoading(true);
      let delayMs = 1500;
      const startedAt = Date.now();
      for (;;) {
        const jitter = Math.floor(Math.random() * 250);
        await new Promise(r => setTimeout(r, delayMs + jitter));
        if (cancelled) return false;
        try {
          const st = await network.inventoryStatus(selectedHuntId);
          if (cancelled) return false;
          if (st.status === 'ready') return true;
          if (Date.now() - startedAt > 5 * 60 * 1000) {
            setError('Host inventory build timed out. Please retry.');
            return false;
          }
          delayMs = Math.min(10000, Math.floor(delayMs * 1.5));
          // still building or none (job may not have started yet) - keep polling
        } catch {
          if (cancelled) return false;
          delayMs = Math.min(10000, Math.floor(delayMs * 1.5));
        }
      }
    };'''
new_text, n = pattern.subn(replacement, text, count=1)
if n != 1:
    raise SystemExit(f"Failed to patch waitUntilReady, matches={n}")
p.write_text(new_text, encoding="utf-8")
print("Patched waitUntilReady")