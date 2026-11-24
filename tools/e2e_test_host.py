#!/usr/bin/env python3
"""모임 '주최자' 입력·표시 검증.

- 새 모임 / 수정 창: 제목 칸 바로 아래 주최자 칸(#evHost), 내 이름 자동 채움
- 저장: 이미 배포된 Apps Script 를 그대로 쓰므로 시트 '제목/메모' 칸에
        `[주최:이름] 제목` 형태로 들어가는지 확인
- 카드: 제목(.titleline) 아래 `👤 주최: 이름` (장소 위)
- 🔗 복사 / 📋 카톡 정산 복사: 주최자 줄 포함, 태그는 노출되지 않음
- 주최자를 비우면 기존 문구와 100% 동일

tools/e2e_test.py 의 시트 목(MOCK)·정적 서버를 그대로 재사용한다.
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

    def card_by_title(page, title):
        for c in page.locator(".card").all():
            try:
                if c.locator(".title").inner_text().strip() == title:
                    return c
            except Exception:
                continue
        return None

    def sheet_title(page, ev_id):
        rows = page.evaluate("() => window.__sheetGrid['모임목록']")
        for r in rows[1:]:
            if r[0] == ev_id:
                return r[5]
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
        page.wait_for_timeout(600)

        # ---------- 계산 함수 단위 확인 ----------
        unit = page.evaluate("""() => ({
          a: window.cpickCore.withHost('이진홍', '화요일 번개게임'),
          b: window.cpickCore.withHost('', '화요일 번개게임'),
          c: window.cpickCore.parseHost('[주최:이진홍] 화요일 번개게임'),
          d: window.cpickCore.parseHost('화요일 번개게임'),
          e: window.cpickCore.displayTitle({type: '정기', title: '[주최:이진홍]'}),
          f: window.cpickCore.displayTitle({type: '번개', title: '[주최:이진홍] 번개 모임'}),
          g: window.cpickCore.hostOf({title: '[주최:  이진홍 ] 삼겹살'}),
          h: window.cpickCore.withHost('이진홍', '가'.repeat(80)).length,
          i: window.cpickCore.hostLine({title: '주최없음'}),
          j: window.cpickCore.parseHost('[주최:' + '가'.repeat(30) + '] 제목').host.length,
          legacyText: window.cpickCore.kakaoText({type: '정기', title: '화요일 번개게임', date: '2026-11-24',
                     time: '19:00', place: '송암', fee: 30000, votes: [{name: '김민수', status: '참석'}]}, 10)
        })""")
        ok("저장 문자열 = [주최:이름] 제목", unit["a"] == "[주최:이진홍] 화요일 번개게임", unit["a"])
        ok("주최자 비면 제목 그대로(기존과 동일)", unit["b"] == "화요일 번개게임", unit["b"])
        ok("[주최:이름] 태그 분해", unit["c"] == {"host": "이진홍", "title": "화요일 번개게임"}, unit["c"])
        ok("태그 없는 제목은 주최자 없음", unit["d"] == {"host": "", "title": "화요일 번개게임"}, unit["d"])
        ok("주최자만 있고 제목 없으면 구분명 표시", unit["e"] == "번개게임", unit["e"])
        ok("예전 기본 제목도 주최자 붙은 채 새 명칭", unit["f"] == "번개회식", unit["f"])
        ok("주최자 앞뒤 공백 정리", unit["g"] == "이진홍", unit["g"])
        ok("시트 80자 한도 안으로 저장", unit["h"] <= 80, unit["h"])
        ok("주최자 없으면 주최 줄 없음", unit["i"] == "", unit["i"])
        ok("주최자 이름은 20자까지만", unit["j"] == 20, unit["j"])

        # ---------- 새 모임 창: 제목 칸 바로 아래 주최자 칸 ----------
        page.fill("#myName", "이진홍")
        page.wait_for_timeout(200)
        page.click("#btnNew")
        page.wait_for_selector("#maskEvent.on")
        ok("주최자 입력칸 표시", page.is_visible("#evHost"))
        ok("주최자 칸 placeholder = 예) 이진홍", page.get_attribute("#evHost", "placeholder") == "예) 이진홍",
           page.get_attribute("#evHost", "placeholder"))
        ok("주최자 칸 maxlength 20", page.get_attribute("#evHost", "maxlength") == "20",
           page.get_attribute("#evHost", "maxlength"))
        ok("주최자 라벨 = 주최자", "주최자" in page.inner_text("#maskEvent .field:has(#evHost) label"),
           page.inner_text("#maskEvent .field:has(#evHost)"))
        geo = page.evaluate("""() => {
          const t = document.querySelector('#evTitle').getBoundingClientRect();
          const h = document.querySelector('#evHost').getBoundingClientRect();
          const f = document.querySelector('#evFee').getBoundingClientRect();
          const tField = document.querySelector('#evTitle').closest('.field');
          const hField = document.querySelector('#evHost').closest('.field');
          return {titleBottom: t.bottom, hostTop: h.top, hostBottom: h.bottom, feeTop: f.top,
                  바로다음: tField.nextElementSibling === hField,
                  순서: Array.from(document.querySelectorAll('#maskEvent .field')).map(x => x.querySelector('label') ? x.querySelector('label').textContent : '')};
        }""")
        ok("주최자 칸이 제목 칸 바로 다음 항목", geo["바로다음"], geo["순서"])
        ok("주최자 라벨이 제목 라벨 바로 뒤",
           geo["순서"].index("주최자") == geo["순서"].index("주최자") and
           any("제목" in x for x in geo["순서"][:geo["순서"].index("주최자")]) and
           geo["순서"][geo["순서"].index("주최자") - 1].startswith("제목"), geo["순서"])
        ok("주최자 칸이 제목 칸 위쪽 바로 밑(간격 60px 이내)", 0 <= geo["hostTop"] - geo["titleBottom"] <= 60, geo)
        ok("주최자 칸이 총 사용료 칸보다 위", geo["hostBottom"] <= geo["feeTop"], geo)
        ok("새 모임이면 내 이름 자동 채움", page.input_value("#evHost") == "이진홍", page.input_value("#evHost"))
        page.wait_for_timeout(350)   # 시트 열림 애니메이션이 끝난 뒤 촬영
        page.screenshot(path=os.path.join(SHOTS, "cpick-att-host-modal.png"))

        # ---------- 주최자 넣고 만들기 ----------
        page.fill("#evPlace", "송암 에어돔 1번코트")
        page.fill("#evTitle", "화요일 번개게임")
        page.fill("#evHost", "박지훈")
        page.fill("#evFee", "50000")
        page.click("#evSave")
        page.wait_for_selector(".card")
        page.wait_for_timeout(400)
        card = card_by_title(page, "화요일 번개게임")
        ok("카드 제목은 순수 제목만(태그 없음)", card is not None, page.inner_text("#list")[:200])
        ok("카드에 '👤 주최: 박지훈' 표시",
           card is not None and "👤 주최: 박지훈" in card.locator(".host").inner_text(),
           card.locator(".host").inner_text() if card and card.locator(".host").count() else None)
        order = page.evaluate("""() => {
          const c = document.querySelector('article.card');
          const tl = c.querySelector('.titleline').getBoundingClientRect();
          const h = c.querySelector('.host').getBoundingClientRect();
          const m = c.querySelector('.meta').getBoundingClientRect();
          const kid = document.querySelector('#list');
          return {tlBottom: tl.bottom, hostTop: h.top, hostLeft: h.left, hostBottom: h.bottom, metaTop: m.top,
                  listScroll: kid.scrollWidth, listClient: kid.clientWidth,
                  hostScroll: c.querySelector('.host').scrollWidth, hostClient: c.querySelector('.host').clientWidth};
        }""")
        ok("주최 줄은 제목(.titleline) 아래", order["hostTop"] >= order["tlBottom"] - 1, order)
        ok("주최 줄은 장소(.meta) 위", order["hostBottom"] <= order["metaTop"], order)
        ok("390px에서 주최 줄이 넘치지 않음",
           order["listScroll"] <= order["listClient"] + 1 and order["hostScroll"] <= order["hostClient"] + 1, order)
        game_id = page.get_attribute("article.card", "data-id")
        ok("시트 제목 칸 = [주최:박지훈] 화요일 번개게임",
           sheet_title(page, game_id) == "[주최:박지훈] 화요일 번개게임", sheet_title(page, game_id))
        page.screenshot(path=os.path.join(SHOTS, "cpick-att-host-card.png"))

        # ---------- 🔗 복사 문구 ----------
        card.locator(".link-copy").click()
        page.wait_for_timeout(500)
        clip = page.evaluate("() => navigator.clipboard.readText()")
        lines = clip.rstrip("\n").split("\n")
        ok("초대 문구 1줄 = 제목(태그 없음)", lines[0] == "🏓 [번개게임] 화요일 번개게임", lines)
        ok("초대 문구에 '👤 주최: 박지훈'", lines[1] == "👤 주최: 박지훈", lines)
        ok("초대 문구에 [주최:...] 태그 없음", "[주최" not in clip, clip)
        ok("초대 문구 날짜 줄·링크 그대로",
           lines[2].startswith("📅 ") and lines[3] == "👇 눌러서 참석 투표하기"
           and lines[4] == base + "/index.html?ev=" + str(game_id), lines)

        # ---------- 📋 카톡 정산 복사 ----------
        page.click(".copy-btn")
        page.wait_for_selector("#maskCopy.on")
        txt = page.input_value("#copyText")
        tl = txt.split("\n")
        ok("정산 문구 1줄 = 🏓 C-PICK 번개게임 정산", tl[0] == "🏓 C-PICK 번개게임 정산", tl[:3])
        ok("정산 문구 제목 줄 다음에 '👤 주최: 박지훈'", tl[1] == "· 화요일 번개게임" and tl[2] == "👤 주최: 박지훈", tl[:4])
        ok("정산 문구에 [주최:...] 태그 없음", "[주최" not in txt, txt)
        page.click("#copyClose")

        # ---------- 수정: 제목/주최자 분리 로드·반영 ----------
        page.click("#btnAdmin")
        page.fill("#pinInput", "0629")
        page.click("#pinOk")
        page.wait_for_timeout(450)
        card = card_by_title(page, "화요일 번개게임")
        card.locator("button[data-edit]").click()
        page.wait_for_selector("#maskEvent.on")
        ok("수정 창 제목 칸 = 순수 제목", page.input_value("#evTitle") == "화요일 번개게임",
           page.input_value("#evTitle"))
        ok("수정 창 주최자 칸 = 박지훈", page.input_value("#evHost") == "박지훈", page.input_value("#evHost"))
        page.fill("#evTitle", "수요일 번개게임")
        page.fill("#evHost", "김민수")
        page.click("#evSave")
        page.wait_for_timeout(500)
        card = card_by_title(page, "수요일 번개게임")
        ok("수정한 제목·주최자 카드 반영",
           card is not None and "👤 주최: 김민수" in card.locator(".host").inner_text(),
           page.inner_text("#list")[:240])
        ok("시트 제목 칸도 갱신", sheet_title(page, game_id) == "[주최:김민수] 수요일 번개게임",
           sheet_title(page, game_id))

        # 수정 창을 다시 열면 바뀐 값이 그대로
        card = card_by_title(page, "수요일 번개게임")
        card.locator("button[data-edit]").click()
        page.wait_for_selector("#maskEvent.on")
        ok("다시 열어도 제목/주최자 분리 유지",
           page.input_value("#evTitle") == "수요일 번개게임" and page.input_value("#evHost") == "김민수",
           [page.input_value("#evTitle"), page.input_value("#evHost")])
        page.click("#evCancel")
        page.wait_for_timeout(200)

        # ---------- 주최자 비우고 만들기 → 기존과 동일 ----------
        page.click("#btnNew")
        page.wait_for_selector("#maskEvent.on")
        ok("새 모임 기본값은 여전히 내 이름", page.input_value("#evHost") == "이진홍", page.input_value("#evHost"))
        page.fill("#evPlace", "스무숲")
        page.fill("#evTitle", "주최없는 번개게임")
        page.fill("#evHost", "")
        page.fill("#evFee", "30000")
        page.click("#evSave")
        page.wait_for_timeout(500)
        plain = card_by_title(page, "주최없는 번개게임")
        ok("주최자를 비우면 주최 줄 없음", plain is not None and plain.locator(".host").count() == 0,
           plain.inner_text()[:200] if plain else None)
        plain_id = plain.get_attribute("data-id")
        ok("주최자 비우면 시트 제목도 순수 제목", sheet_title(page, plain_id) == "주최없는 번개게임",
           sheet_title(page, plain_id))
        plain.locator(".link-copy").click()
        page.wait_for_timeout(450)
        plain_clip = page.evaluate("() => navigator.clipboard.readText()")
        pl = plain_clip.rstrip("\n").split("\n")
        ok("주최자 없으면 초대 문구 기존과 100% 동일",
           pl == ["🏓 [번개게임] 주최없는 번개게임", pl[1], "👇 눌러서 참석 투표하기",
                  base + "/index.html?ev=" + str(plain_id)] and pl[1].startswith("📅 "), pl)
        page.fill("#myName", "김민수")
        plain.locator('.vote[data-status="참석"]').click()
        page.wait_for_timeout(400)
        card_by_title(page, "주최없는 번개게임").locator(".copy-btn").click()
        page.wait_for_selector("#maskCopy.on")
        plain_txt = page.input_value("#copyText")
        ok("주최자 없으면 정산 문구에 주최 줄 없음", "👤 주최:" not in plain_txt, plain_txt)
        ok("주최자 없으면 정산 문구 기존 구조 그대로",
           plain_txt.split("\n")[0] == "🏓 C-PICK 번개게임 정산"
           and plain_txt.split("\n")[1] == "· 주최없는 번개게임"
           and any(l.startswith("📅 ") for l in plain_txt.split("\n"))
           and "총 사용료 30,000원" in plain_txt, plain_txt)
        page.click("#copyClose")

        # ---------- 주최자만 넣고 제목 비우기 ----------
        page.click("#btnNew")
        page.wait_for_selector("#maskEvent.on")
        page.fill("#evTitle", "")
        page.fill("#evHost", "최유진")
        page.fill("#evPlace", "공지천")
        page.click("#evSave")
        page.wait_for_timeout(500)
        only = card_by_title(page, "번개게임")
        ok("제목이 없으면 카드 제목은 구분명(번개게임)", only is not None, page.inner_text("#list")[:240])
        ok("주최자만 있어도 주최 줄 표시",
           only is not None and "👤 주최: 최유진" in only.locator(".host").inner_text(),
           only.locator(".host").inner_text() if only and only.locator(".host").count() else None)
        only_id = only.get_attribute("data-id")
        ok("시트에는 [주최:최유진] 만 저장", sheet_title(page, only_id) == "[주최:최유진]", sheet_title(page, only_id))

        # ---------- 다른 기기(같은 시트)에서도 주최자 보임 + 태그 노출 없음 ----------
        page2 = ctx.new_page()
        page2.on("dialog", lambda d: d.accept())
        page2.goto(url)
        page2.wait_for_timeout(800)
        page2.click("#btnAdmin")
        page2.fill("#pinInput", "0629")
        page2.click("#pinOk")
        page2.wait_for_timeout(450)
        other = card_by_title(page2, "수요일 번개게임")
        ok("다른 화면에서도 👤 주최: 김민수 표시",
           other is not None and "👤 주최: 김민수" in other.locator(".host").inner_text(),
           page2.inner_text("#list")[:240])
        ok("다른 화면 어디에도 [주최: 태그 노출 없음", "[주최" not in page2.inner_text("body"),
           page2.inner_text("body")[:300])
        other.locator("button[data-edit]").click()
        page2.wait_for_selector("#maskEvent.on")
        ok("다른 화면 수정 창도 제목/주최자 분리",
           page2.input_value("#evTitle") == "수요일 번개게임" and page2.input_value("#evHost") == "김민수",
           [page2.input_value("#evTitle"), page2.input_value("#evHost")])
        page2.close()

        # ---------- 수정에서 주최자 지우기 → 표시·시트에서도 사라짐 ----------
        named = card_by_title(page, "수요일 번개게임")
        named.locator("button[data-edit]").click()
        page.wait_for_selector("#maskEvent.on")
        page.fill("#evHost", "")
        page.click("#evSave")
        page.wait_for_timeout(500)
        named = card_by_title(page, "수요일 번개게임")
        ok("수정에서 주최자를 지우면 주최 줄 사라짐",
           named is not None and named.locator(".host").count() == 0,
           named.inner_text()[:200] if named else None)
        ok("주최자를 지우면 시트 제목도 태그 없이", sheet_title(page, game_id) == "수요일 번개게임",
           sheet_title(page, game_id))

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
