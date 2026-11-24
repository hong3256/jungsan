#!/usr/bin/env python3
"""모임 카드 제목 옆 '🔗 복사'(카톡 초대 문구 + 딥링크 ?ev=모임ID) 검증.

- tools/e2e_test.py 의 시트 목(MOCK)·정적 서버를 그대로 재사용한다.
- 모바일 390px · 모의 Apps Script 실행 상태에서 실제 화면을 띄워 확인한다.
"""
import json
import os
import sys

from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import e2e_test  # noqa: E402  (MOCK, serve 재사용)

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GS = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(HERE), "downloads", "cpick-attendance-apps-script.txt")
SHOTS = os.path.join(os.path.dirname(HERE), "downloads")


def main():
    code = open(GS, encoding="utf-8").read()
    httpd, port = e2e_test.serve(HERE)
    base = f"http://127.0.0.1:{port}"
    url = base + "/index.html?sync=/mock"

    results = []

    def ok(name, cond, detail=None):
        results.append((bool(cond), name, detail))
        print(("통과  " if cond else "실패  ") + name + ("" if cond or detail is None else
              " :: " + json.dumps(detail, ensure_ascii=False)[:400]))

    console_errors = []

    def card_with(page, text):
        for c in page.locator(".card").all():
            try:
                if text in c.inner_text():
                    return c
            except Exception:
                continue
        return None

    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2,
                                  is_mobile=True, has_touch=True)
        ctx.grant_permissions(["clipboard-read", "clipboard-write"], origin=base)
        ctx.add_init_script("(() => { const fn = " + e2e_test.MOCK + "; fn(" + json.dumps(code) + "); })()")

        page = ctx.new_page()
        page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: console_errors.append("pageerror: " + str(e)))
        page.on("dialog", lambda d: d.accept())
        page.goto(url)
        page.wait_for_timeout(700)

        # ---------- 모임 두 개 만들기 ----------
        page.click("#btnNew")
        page.fill("#evPlace", "송암 에어돔 1번코트")
        page.fill("#evTitle", "화요일 번개게임")
        page.fill("#evFee", "50000")
        page.click("#evSave")
        page.wait_for_selector(".card")
        page.wait_for_timeout(400)
        game = card_with(page, "화요일 번개게임")
        ok("번개게임 카드 생성", game is not None, page.inner_text("#list")[:200])
        game_id = page.get_attribute("article.card", "data-id")

        page.click("#btnNew")
        page.click('#evType button[data-type="번개"]')
        page.fill("#evPlace", "스무숲")
        page.fill("#evTitle", "삼겹살 번개회식")
        page.click("#evSave")
        page.wait_for_timeout(500)
        page.click('#tabs button[data-tab="전체"]')
        page.wait_for_timeout(200)
        page.click('#tabs button[data-tab="번개"]')
        page.wait_for_timeout(250)
        rice = card_with(page, "삼겹살 번개회식")
        rice_id = rice.get_attribute("data-id")
        ok("번개회식 카드 생성", rice is not None and bool(rice_id), page.inner_text("#list")[:200])

        # ---------- 제목 옆 🔗 복사 버튼 배치(390px) ----------
        page.click('#tabs button[data-tab="정기"]')
        page.wait_for_timeout(250)
        card = card_with(page, "화요일 번개게임")
        ok("카드 제목 옆 🔗 복사 버튼", card.locator(".titleline .link-copy").count() == 1,
           card.inner_text()[:160])
        ok("버튼 글자 = 🔗 복사", "🔗" in card.locator(".link-copy").inner_text()
           and "복사" in card.locator(".link-copy").inner_text(), card.locator(".link-copy").inner_text())
        geo = page.evaluate("""() => {
          const c = document.querySelector('article.card');
          const tl = c.querySelector('.titleline'), t = c.querySelector('.title'), b = c.querySelector('.link-copy');
          const cr = c.getBoundingClientRect(), tr = t.getBoundingClientRect(), br = b.getBoundingClientRect();
          return {card: [cr.left, cr.right], title: [tr.left, tr.right, tr.top, tr.bottom],
                  btn: [br.left, br.right, br.top, br.bottom], tl: [tl.scrollWidth, tl.clientWidth],
                  sameRow: br.top < tr.bottom && tr.top < br.bottom, gap: br.left - tr.right};
        }""")
        ok("390px에서 제목·버튼이 한 줄에 나란히(넘침 없음)",
           geo["sameRow"] and geo["tl"][0] <= geo["tl"][1] + 1 and geo["btn"][1] <= geo["card"][1] + 1
           and geo["card"][0] <= geo["btn"][0], geo)
        ok("버튼이 제목 오른쪽(간격 4px 이상)", geo["gap"] >= 4, geo)
        page.screenshot(path=os.path.join(SHOTS, "cpick-att-share-mobile.png"))

        # ---------- 🔗 복사 → 클립보드 문구 ----------
        card.locator(".link-copy").click()
        page.wait_for_timeout(500)
        clip = page.evaluate("() => navigator.clipboard.readText()")
        lines = clip.rstrip("\n").split("\n")
        ok("복사 문구 1줄 = 🏓 [번개게임] 화요일 번개게임", lines[0] == "🏓 [번개게임] 화요일 번개게임", lines)
        ok("복사 문구 2줄 = 📅 날짜 시간 · 장소",
           lines[1].startswith("📅 ") and "19:00 · 송암 에어돔 1번코트" in lines[1], lines[1] if len(lines) > 1 else lines)
        ok("복사 문구 3줄 = 👇 눌러서 참석 투표하기", lines[2] == "👇 눌러서 참석 투표하기", lines)
        ok("복사 문구 4줄 = 앱주소?ev=모임ID",
           lines[3] == base + "/index.html?ev=" + str(game_id), lines[3] if len(lines) > 3 else lines)
        ok("복사 성공 토스트", "모임 링크를 복사했어요" in page.inner_text("#toast"), page.inner_text("#toast"))
        ok("복사 모달은 열리지 않음(자동 복사 성공)", not page.is_visible("#maskShare"))

        # 장소가 없으면 ' · ' 없이
        page.evaluate("() => { const ev = window.cpickCore; }")
        noplace = page.evaluate("""() => window.cpickCore.inviteText({id: 'E1', type: '번개', title: '삼겹살',
            date: '2026-11-24', time: '19:00', place: ''})""")
        nol = noplace.rstrip("\n").split("\n")
        ok("장소 없으면 ' · ' 없이 날짜·시간만", nol[1].startswith("📅 ") and "·" not in nol[1], nol[1])
        ok("번개회식은 🍻 [번개회식]", nol[0] == "🍻 [번개회식] 삼겹살", nol[0])
        bare = page.evaluate("""() => window.cpickCore.inviteText({id: 'E2', type: '정기', title: '정기 모임',
            date: '2026-11-24', time: '19:00', place: ''})""")
        ok("제목이 없으면 구분만(중복 없음)", bare.split("\n")[0] == "🏓 [번개게임]", bare.split("\n")[0])

        # ---------- 자동 복사가 막힌 경우 → 직접 복사 창 ----------
        page.evaluate("""() => { const c = navigator.clipboard;
            window.__realWrite = c.writeText.bind(c);
            Object.defineProperty(c, 'writeText', {configurable: true, value: () => Promise.reject(new Error('blocked'))}); }""")
        card = card_with(page, "화요일 번개게임")
        card.locator(".link-copy").click()
        page.wait_for_timeout(600)
        ok("복사가 막히면 직접 복사 창 표시", page.is_visible("#maskShare"), page.inner_text("#toast"))
        share_txt = page.input_value("#shareText")
        ok("창 안 문구에 제목·링크", "화요일 번개게임" in share_txt and "?ev=" + str(game_id) in share_txt, share_txt)
        ok("안내 토스트(복사됐다고 속이지 않음)", "자동 복사가 안 돼요" in page.inner_text("#toast"), page.inner_text("#toast"))
        page.screenshot(path=os.path.join(SHOTS, "cpick-att-share-fallback.png"))
        page.click("#shareClose")
        page.evaluate("""() => { Object.defineProperty(navigator.clipboard, 'writeText',
            {configurable: true, value: window.__realWrite}); }""")

        # ---------- ?ev=모임ID (번개회식) → 탭 자동 전환 + 카드 강조 ----------
        target = base + "/index.html?ev=" + str(rice_id) + "&sync=/mock"
        page.goto(target)
        page.wait_for_timeout(900)
        on_tab = page.inner_text("#tabs .tab.on")
        ok("?ev=번개회식 → 번개회식 탭 자동 선택", "번개회식" in on_tab, on_tab)
        rc = card_with(page, "삼겹살 번개회식")
        ok("?ev= 해당 모임 카드 표시", rc is not None, page.inner_text("#list")[:200])
        ok("?ev= 카드 잠깐 강조(hl)", rc is not None and "hl" in (rc.get_attribute("class") or ""),
           rc.get_attribute("class") if rc else None)
        page.screenshot(path=os.path.join(SHOTS, "cpick-att-share-deeplink.png"))
        page.wait_for_timeout(3200)
        rc = card_with(page, "삼겹살 번개회식")
        ok("강조는 2~3초 뒤 사라짐", rc is not None and "hl" not in (rc.get_attribute("class") or ""),
           rc.get_attribute("class") if rc else None)

        # ---------- ?ev=정기 모임: 스크롤 ----------
        for i in range(5):
            page.goto(url)
            page.wait_for_timeout(500)
            page.click("#btnNew")
            page.fill("#evDate", "2026-12-%02d" % (10 + i))
            page.fill("#evTitle", "겨울 번개게임 %d" % (i + 1))
            page.click("#evSave")
            page.wait_for_timeout(350)
        page.goto(url)
        page.wait_for_timeout(600)
        last = card_with(page, "겨울 번개게임 5")
        last_id = last.get_attribute("data-id")
        page.goto(base + "/index.html?ev=" + str(last_id) + "&sync=/mock")
        page.wait_for_timeout(1300)
        pos = page.evaluate("""(id) => {
          const el = document.querySelector('article.card[data-id="' + id + '"]');
          if (!el) return null;
          const r = el.getBoundingClientRect();
          return {scrollY: window.scrollY, top: Math.round(r.top), bottom: Math.round(r.bottom),
                  h: window.innerHeight, hl: el.className};
        }""", str(last_id))
        ok("아래쪽 모임도 화면 안으로 스크롤", pos is not None and pos["scrollY"] > 0
           and pos["top"] < pos["h"] and pos["bottom"] > 0, pos)
        ok("스크롤한 카드도 강조", pos is not None and "hl" in pos["hl"], pos)
        page.screenshot(path=os.path.join(SHOTS, "cpick-att-share-deeplink-scroll.png"))

        # ---------- ?ev=없는 모임 → 안내 ----------
        page.goto(base + "/index.html?ev=NOPE&sync=/mock")
        page.wait_for_timeout(1200)
        ok("없는 모임 → '찾으려는 모임이 없어요' 안내",
           "찾으려는 모임이 없어요" in page.inner_text("#toast"), page.inner_text("#toast"))
        ok("없는 모임이어도 앱은 정상(목록 표시)", page.locator(".card").count() > 0,
           page.locator(".card").count())

        # ---------- 콘솔 오류 ----------
        real_errors = [e for e in console_errors if "favicon" not in e.lower()]
        ok("콘솔 오류 0건", len(real_errors) == 0, real_errors[:5])

        browser.close()

    httpd.shutdown()
    passed = sum(1 for x in results if x[0])
    print(f"\n=== {passed}/{len(results)} 통과 ===")
    for good, name, detail in results:
        if not good:
            print("  실패:", name, json.dumps(detail, ensure_ascii=False)[:300] if detail is not None else "")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
