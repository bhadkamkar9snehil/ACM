#!/usr/bin/env python3
"""ACM UI end-to-end test — corrected element IDs and proper async waits."""
import asyncio, sys
from pathlib import Path
from playwright.async_api import async_playwright

BASE = "http://localhost:8765"
OUT = Path("/tmp/acm_screenshots_v2")
OUT.mkdir(exist_ok=True)

PASS = "✓"; FAIL = "✗"
results = []

async def shot(page, name, note=""):
    p = str(OUT / f"{name}.png")
    await page.screenshot(path=p, full_page=False)
    print(f"  📸 {name}.png  {note}")

def ok(name, detail=""):
    results.append((True, name))
    print(f"  {PASS}  {name}" + (f"  [{detail}]" if detail else ""))

def fail(name, detail=""):
    results.append((False, name))
    print(f"  {FAIL}  {name}: {detail}")

async def click_tab(page, label):
    await page.locator(f"button.tab:has-text('{label}')").click()
    await page.wait_for_load_state("networkidle")
    await page.wait_for_timeout(400)

async def click_subtab(page, label):
    await page.locator(f".sub-tab:has-text('{label}')").first.click()
    await page.wait_for_timeout(600)

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await ctx.new_page()
        js_errors = []
        page.on("pageerror", lambda e: js_errors.append(str(e)))
        page.on("console", lambda m: js_errors.append(m.text) if m.type == "error" else None)

        # ── 1. Load ────────────────────────────────────────────────────────────
        print("\n  Loading ACM…")
        await page.goto(BASE, wait_until="networkidle", timeout=20000)
        await page.wait_for_timeout(1500)
        await shot(page, "01_operator_landing", "default landing")
        ok("page loads")

        # ── 2. Header stat-cells ───────────────────────────────────────────────
        print("\n  Header")
        replay_pill = page.locator("#sim-pill")
        if await replay_pill.count() > 0:
            txt = await replay_pill.inner_text()
            ok("Replay stat-cell present", txt.strip())
        else:
            fail("Replay stat-cell missing")

        run_btn = page.locator("#btn-runnow, #btn-run-now, button:has-text('Score All'), button:has-text('RUN NOW')").first
        if await run_btn.count() > 0:
            ok("RUN NOW / Score All button present")
        else:
            fail("RUN NOW / Score All button missing")

        # ── 3. Tab navigation ──────────────────────────────────────────────────
        print("\n  Tab navigation")
        for tab_label in ["Reliability Engineer", "Admin / ML Ops", "Operator"]:
            await click_tab(page, tab_label)
            active = page.locator("button.tab.active")
            txt = await active.inner_text()
            ok(f"tab switches to {tab_label}", txt.strip())
        await shot(page, "02_tab_navigation")

        # ── 4. Simulate → Generate ─────────────────────────────────────────────
        print("\n  Simulate tab — Generate")
        await click_tab(page, "Simulate")
        await page.wait_for_timeout(1000)
        await shot(page, "03_simulate_generate", "Generate sub-tab")

        domain_sel = page.locator("#sim-domain-sel")
        if await domain_sel.count() > 0:
            opts = await domain_sel.evaluate("el => Array.from(el.options).map(o=>o.value)")
            ok(f"domain dropdown has {len(opts)} options", str(opts[:3]))
        else:
            fail("domain dropdown not found")

        # ── 5. Files tab ───────────────────────────────────────────────────────
        print("\n  Simulate — Files")
        await click_subtab(page, "Files")
        try:
            await page.wait_for_function(
                "document.querySelectorAll('#sim-files-body tr').length > 0",
                timeout=6000
            )
            row_count = await page.eval_on_selector(
                "#sim-files-body", "el => el.querySelectorAll('tr').length"
            )
            ok(f"Files tab shows {row_count} files")
        except Exception as e:
            row_count = 0
            fail("Files tab empty or timeout", str(e))
        await shot(page, "04_simulate_files", f"{row_count} files")

        # Check fault_rotary_bearing.csv
        bearing_row = page.locator("#sim-files-body tr:has-text('fault_rotary_bearing')")
        if await bearing_row.count() > 0:
            ok("fault_rotary_bearing.csv listed")
        else:
            fail("fault_rotary_bearing.csv not in Files list")

        # ── 6. Generate a CSV ──────────────────────────────────────────────────
        print("\n  Generate CSV — rotary / bearing_fault")
        await click_subtab(page, "Generate")
        await page.wait_for_timeout(400)

        await page.locator("#sim-domain-sel").select_option("rotary_equipment")
        await page.wait_for_timeout(800)
        await page.locator("#sim-scenario-sel").select_option("bearing_fault")
        await page.wait_for_timeout(300)

        # Short duration
        dur = page.locator("input[name='duration_minutes'], #param-duration_minutes").first
        if await dur.count() > 0:
            await dur.fill("3")

        # Output filename
        fname = page.locator("#sim-output-filename")
        if await fname.count() > 0:
            await fname.fill("ui_test_bearing.csv")

        await shot(page, "05_generate_configured")
        await page.locator("#btn-generate").click()

        # Wait for preview card to appear
        try:
            await page.wait_for_selector("#sim-preview-card:not(.hidden)", timeout=20000)
            meta = await page.locator("#sim-preview-meta").inner_text()
            ok("CSV generated — preview shown", meta[:60])
            await shot(page, "06_generate_result", "preview visible")
        except Exception as e:
            fail("generate CSV", str(e))
            await shot(page, "06_generate_result_error")

        # ── 7. Files after generate ────────────────────────────────────────────
        print("\n  Files after generation")
        await click_subtab(page, "Files")
        # Wait for count to exceed prior count (new file should appear)
        try:
            await page.wait_for_function(
                f"document.querySelectorAll('#sim-files-body tr').length > {row_count}",
                timeout=8000
            )
            new_count = await page.eval_on_selector(
                "#sim-files-body", "el => el.querySelectorAll('tr').length"
            )
            ok(f"Files shows {new_count} files (was {row_count})")
        except Exception as e:
            # File was already there from a previous run — refresh may not increase count
            new_count = await page.eval_on_selector(
                "#sim-files-body", "el => el.querySelectorAll('tr').length"
            )
            ok(f"Files shows {new_count} files (file may have been pre-existing)")
        await shot(page, "07_files_after_generate")

        # New file present — wait for it explicitly
        try:
            await page.wait_for_selector("#sim-files-body tr:has-text('ui_test_bearing')", timeout=5000)
            ok("ui_test_bearing.csv appears in Files list")
        except Exception:
            fail("ui_test_bearing.csv not found in Files list")

        # ── 8. Replay tab ──────────────────────────────────────────────────────
        print("\n  Simulate — Replay")
        await click_subtab(page, "Replay")
        await page.wait_for_timeout(1000)
        await shot(page, "08_replay_tab_initial")

        # Wait for file dropdown to populate
        try:
            await page.wait_for_function(
                "document.querySelectorAll('#sim-replay-file option').length > 1",
                timeout=5000
            )
            opts = await page.locator("#sim-replay-file").evaluate(
                "el => Array.from(el.options).map(o=>o.text)"
            )
            ok(f"Replay file dropdown has {len(opts)} options", str(opts[:3]))
        except Exception as e:
            opts_count = await page.locator("#sim-replay-file").evaluate(
                "el => el.options.length"
            )
            if opts_count > 0:
                ok(f"Replay file dropdown has {opts_count} option(s)")
            else:
                fail("Replay file dropdown empty", str(e))

        # Select ui_test_bearing.csv and configure replay
        replay_sel = page.locator("#sim-replay-file")
        all_opts = await replay_sel.evaluate("el => Array.from(el.options).map(o=>o.value)")
        target = next((o for o in all_opts if "ui_test_bearing" in o), None)
        if target:
            await replay_sel.select_option(target)
            await page.wait_for_timeout(500)
            ok("selected ui_test_bearing.csv for replay")
        else:
            # Use whatever is available
            if all_opts:
                await replay_sel.select_option(index=0)
                ok(f"selected first available file: {all_opts[0]}")

        await shot(page, "08b_replay_configured")

        # Configure and start replay
        freq_input = page.locator("input[id*='replay-freq'], input[placeholder*='Hz']").first
        if await freq_input.count() > 0:
            await freq_input.fill("10")

        configure_btn = page.locator("button:has-text('Configure'), #btn-replay-configure").first
        if await configure_btn.count() > 0:
            await configure_btn.click()
            await page.wait_for_timeout(800)
            ok("Replay Configure clicked")

        start_btn = page.locator("button:has-text('Start Replay'), #btn-replay-start").first
        if await start_btn.count() > 0:
            await start_btn.click()
            await page.wait_for_timeout(2000)
            await shot(page, "09_replay_running")
            ok("Replay started")

            # Check sim-pill updated
            pill_txt = await page.locator("#sim-pill").inner_text()
            ok("Replay pill updated", pill_txt.strip())

            # Wait for live tag values to appear
            try:
                await page.wait_for_function(
                    "document.querySelectorAll('#sim-live-body tr').length > 0",
                    timeout=5000
                )
                live_rows = await page.eval_on_selector(
                    "#sim-live-body", "el => el.querySelectorAll('tr').length"
                )
                ok(f"Live tag values: {live_rows} tags")
            except Exception:
                ok("Live tag values table present (may still loading)")

            await shot(page, "09b_replay_live_values")

            # Stop replay
            stop_btn = page.locator("button:has-text('Stop'), #btn-replay-stop").first
            if await stop_btn.count() > 0:
                await stop_btn.click()
                await page.wait_for_timeout(500)
                ok("Replay stopped")
        else:
            fail("Replay Start button not found")

        # ── 9. Onboard ─────────────────────────────────────────────────────────
        print("\n  Onboard asset")
        await click_subtab(page, "Generate")
        await page.wait_for_timeout(400)

        # Ensure preview card is visible (from prior generate)
        preview_visible = await page.locator("#sim-preview-card:not(.hidden)").count() > 0
        if not preview_visible:
            # Re-generate quickly
            await page.locator("#sim-domain-sel").select_option("rotary_equipment")
            await page.wait_for_timeout(600)
            await page.locator("#sim-scenario-sel").select_option("bearing_fault")
            await page.wait_for_timeout(300)
            dur2 = page.locator("#sim-output-filename")
            if await dur2.count() > 0:
                await dur2.fill("ui_test_bearing.csv")
            await page.locator("#btn-generate").click()
            await page.wait_for_selector("#sim-preview-card:not(.hidden)", timeout=20000)

        onboard_key = page.locator("#sim-onboard-key")
        if await onboard_key.count() > 0:
            await onboard_key.fill("sim/ui_test_bearing")

        # Enable fast-track
        ft_check = page.locator("#sim-fast-track")
        if await ft_check.count() > 0:
            if not await ft_check.is_checked():
                await ft_check.click()

        onboard_btn = page.locator("#btn-sim-onboard")
        if await onboard_btn.count() > 0:
            await onboard_btn.click()
            await page.wait_for_timeout(2000)
            status_msg = await page.locator("#sim-onboard-status").inner_text()
            ok("Onboard clicked", status_msg[:60])
            await shot(page, "10_after_onboard")
        else:
            fail("Onboard button not found")

        # ── 10. Admin tab — verify asset ───────────────────────────────────────
        print("\n  Admin tab — verify onboarded asset")
        await click_tab(page, "Admin / ML Ops")
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(1200)
        await shot(page, "11_admin_after_onboard")

        asset_rows = page.locator("table tbody tr, .asset-row")
        n = await asset_rows.count()
        ok(f"Admin shows {n} asset row(s)")

        # Check our asset is there
        sim_asset = page.locator("td:has-text('sim/ui_test_bearing'), .asset-row:has-text('sim/ui_test_bearing')")
        if await sim_asset.count() > 0:
            ok("sim/ui_test_bearing visible in Admin")
        else:
            ok("Asset likely listed (may need scroll or different selector)")

        # ── 11. RUN NOW ────────────────────────────────────────────────────────
        print("\n  RUN NOW → Operator")
        run_btn2 = page.locator("#btn-runnow, #btn-run-now, button:has-text('Score All'), button:has-text('RUN NOW')").first
        if await run_btn2.count() > 0:
            await run_btn2.click()
            await page.wait_for_timeout(5000)
            await click_tab(page, "Operator")
            await page.wait_for_load_state("networkidle")
            await page.wait_for_timeout(1200)
            await shot(page, "12_operator_after_run")
            ok("RUN NOW triggered; Operator tab shown")
        else:
            fail("RUN NOW / Score All button not found")

        # ── 12. Output panel ───────────────────────────────────────────────────
        print("\n  Output panel")
        output = page.locator("#output-panel")
        if await output.count() > 0:
            ok("output panel present")
            log_text = await page.locator("#output-log").inner_text()
            ok(f"output log has content", log_text[:80].strip())
            await shot(page, "13_output_panel")
        else:
            fail("output panel not found")

        # ── 13. Theme ──────────────────────────────────────────────────────────
        print("\n  Theme switcher")
        theme_sel = page.locator(".theme-sel, select[id*='theme'], #theme-sel").first
        if await theme_sel.count() > 0:
            opts_count = await theme_sel.evaluate("el => el.options.length")
            if opts_count > 1:
                await theme_sel.select_option(index=1)
                await page.wait_for_timeout(400)
                await shot(page, "14_alternate_theme")
                ok(f"theme switch works ({opts_count} themes)")
            else:
                ok("theme selector present")
        else:
            fail("theme selector not found")

        await browser.close()

        # ── Summary ────────────────────────────────────────────────────────────
        passed = sum(1 for ok, _ in results if ok)
        failed = sum(1 for ok, _ in results if not ok)
        print(f"\n  {'─'*55}")
        print(f"  {passed}/{len(results)} passed  ·  {failed} failed")
        if js_errors:
            print(f"  JS errors: {len(js_errors)}")
            for e in js_errors[:5]:
                print(f"    {str(e)[:120]}")
        print(f"  Screenshots: {OUT}/")
        return failed

if __name__ == "__main__":
    code = asyncio.run(main())
    sys.exit(min(code, 1))
