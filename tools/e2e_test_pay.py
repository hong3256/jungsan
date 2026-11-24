#!/usr/bin/env python3
"""정산 문구의 '송금 안내(계좌번호 / 카톡으로 보내주세요)' 선택 기능 검증.

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

ACCT = "3333-00-0000000"
HOLDER = "김예시"


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

    def last_line(page):
        return page.input_value("#copyText").rstrip("\n").split("\n")[-1]

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

        # ---------- 모임 하나 만들고 3명 참석(3만원 ÷ 3명 = 1만원) ----------
        page.click("#btnNew")
        page.fill("#evPlace", "송암 에어돔 1번코트")
        page.fill("#evTitle", "화요일 번개게임")
        page.fill("#evFee", "30000")
        page.click("#evSave")
        page.wait_for_selector(".card")
        page.wait_for_timeout(300)
        for n in ["김민수", "이서연", "박지훈"]:
            page.fill("#myName", n)
            page.click('.card .vote[data-status="참석"]')
            page.wait_for_timeout(300)
        ok("3명 참석 → 1인당 10,000원", "10,000원" in page.inner_text(".perline"),
           page.inner_text(".perline"))

        # ---------- 정산 문구 열기 (처음) ----------
        page.click(".copy-btn")
        page.wait_for_selector("#maskCopy.on")
        ok("송금 안내 선택 버튼 2개", page.locator("#payMode button").count() == 2,
           page.locator("#payMode button").count())
        ok("버튼 문구 — 🏦 계좌번호 입력 / 💬 카톡으로 보내주세요",
           page.locator('#payMode button[data-pay="acct"]').inner_text().strip() == "🏦 계좌번호 입력"
           and page.locator('#payMode button[data-pay="kakao"]').inner_text().strip() == "💬 카톡으로 보내주세요",
           page.inner_text("#payMode"))
        ok("처음에는 🏦 계좌번호 입력이 선택",
           page.locator('#payMode button[data-pay="acct"]').get_attribute("class").find("on") >= 0)
        ok("계좌·예금주 입력칸 표시", page.is_visible("#payAcct") and page.is_visible("#payHolder"))
        ok("처음 열 때 자동 복사 — 클립보드 = 문구", page.evaluate("() => navigator.clipboard.readText()").strip()
           == page.input_value("#copyText").strip())
        ok("계좌가 비어 있으면 안내 한 줄", last_line(page) == "🏦 입금 계좌: (계좌번호를 넣어 주세요)", last_line(page))
        ok("기존 정산 내용 유지(제목·총액·1인당)",
           all(k in page.input_value("#copyText") for k in ["화요일 번개게임", "총 사용료 30,000원", "참석 3명",
                                                          "1인당 10,000원"]), page.input_value("#copyText"))
        page.screenshot(path=os.path.join(SHOTS, "cpick-att-pay-empty-acct.png"))

        # ---------- 계좌·예금주 입력 → 문구 실시간 반영 ----------
        page.fill("#payAcct", ACCT)
        page.wait_for_timeout(80)
        ok("계좌번호 먼저 넣으면 예금주 없이 표시", last_line(page) == "🏦 입금 계좌: " + ACCT, last_line(page))
        page.fill("#payHolder", HOLDER)
        page.wait_for_timeout(120)
        ok("계좌 + 예금주 반영", last_line(page) == "🏦 입금 계좌: " + ACCT + " " + HOLDER, last_line(page))
        ok("문구가 계좌 안내로 끝남(뒤에 빈 줄 없음)",
           page.input_value("#copyText").rstrip("\n").endswith("🏦 입금 계좌: " + ACCT + " " + HOLDER),
           repr(page.input_value("#copyText")[-60:]))
        saved = page.evaluate("""() => ({mode: localStorage.getItem('cpick.payMode'),
            acct: localStorage.getItem('cpick.payAcct'), holder: localStorage.getItem('cpick.payHolder')})""")
        ok("계좌·예금주·방식이 기기에 저장",
           saved == {"mode": "acct", "acct": ACCT, "holder": HOLDER}, saved)
        page.screenshot(path=os.path.join(SHOTS, "cpick-att-pay-acct.png"))

        # 📋 문구 복사 버튼
        page.click("#copyOk")
        page.wait_for_timeout(250)
        ok("📋 문구 복사 → 클립보드", page.evaluate("() => navigator.clipboard.readText()")
           == page.input_value("#copyText"), page.evaluate("() => navigator.clipboard.readText()")[-60:])
        ok("복사 토스트", "복사했어요" in page.inner_text("#toast"), page.inner_text("#toast"))
        page.click("#copyClose")
        page.wait_for_timeout(200)

        # ---------- 다시 열기 → 값 유지 ----------
        page.click(".copy-btn")
        page.wait_for_selector("#maskCopy.on")
        ok("모달 다시 열면 계좌·예금주 자동 채움",
           page.input_value("#payAcct") == ACCT and page.input_value("#payHolder") == HOLDER,
           [page.input_value("#payAcct"), page.input_value("#payHolder")])
        ok("모달 다시 열어도 문구에 계좌 포함", last_line(page) == "🏦 입금 계좌: " + ACCT + " " + HOLDER,
           last_line(page))
        page.click("#copyClose")
        page.wait_for_timeout(150)

        # ---------- 새로고침(새로 열기) 후에도 유지 ----------
        page.reload()
        page.wait_for_timeout(900)
        page.click(".copy-btn")
        page.wait_for_selector("#maskCopy.on")
        ok("새로고침 후에도 계좌·예금주 유지(localStorage)",
           page.input_value("#payAcct") == ACCT and page.input_value("#payHolder") == HOLDER,
           [page.input_value("#payAcct"), page.input_value("#payHolder")])
        ok("새로고침 후 문구에 계좌 포함", last_line(page) == "🏦 입금 계좌: " + ACCT + " " + HOLDER, last_line(page))

        # ---------- 💬 카톡으로 보내주세요 로 전환 ----------
        page.click('#payMode button[data-pay="kakao"]')
        page.wait_for_timeout(150)
        ok("카톡 선택 시 계좌 입력칸 숨김", not page.is_visible("#payFields"))
        ok("카톡 선택 시 버튼 강조 이동",
           "on" in page.locator('#payMode button[data-pay="kakao"]').get_attribute("class")
           and "on" not in page.locator('#payMode button[data-pay="acct"]').get_attribute("class"))
        ok("카톡 문구 한 줄", last_line(page) == "💬 카톡으로 보내주세요", last_line(page))
        ok("카톡 모드에는 계좌 안내 없음", "입금 계좌" not in page.input_value("#copyText"),
           page.input_value("#copyText")[-80:])
        ok("카톡 모드 저장", page.evaluate("() => localStorage.getItem('cpick.payMode')") == "kakao",
           page.evaluate("() => localStorage.getItem('cpick.payMode')"))
        page.click("#copyOk")
        page.wait_for_timeout(200)
        ok("카톡 모드 문구 복사", page.evaluate("() => navigator.clipboard.readText()")
           == page.input_value("#copyText"))
        page.screenshot(path=os.path.join(SHOTS, "cpick-att-pay-kakao.png"))
        page.click("#copyClose")
        page.wait_for_timeout(150)

        # 카톡 모드 유지 확인
        page.click(".copy-btn")
        page.wait_for_selector("#maskCopy.on")
        ok("다시 열어도 카톡 방식 유지",
           "on" in page.locator('#payMode button[data-pay="kakao"]').get_attribute("class")
           and not page.is_visible("#payFields") and last_line(page) == "💬 카톡으로 보내주세요",
           last_line(page))

        # ---------- 다시 계좌로 (값 그대로) ----------
        page.click('#payMode button[data-pay="acct"]')
        page.wait_for_timeout(150)
        ok("계좌로 되돌리면 입력칸·값 복귀", page.is_visible("#payFields")
           and page.input_value("#payAcct") == ACCT and page.input_value("#payHolder") == HOLDER,
           [page.input_value("#payAcct"), page.input_value("#payHolder")])
        ok("계좌 안내 복귀", last_line(page) == "🏦 입금 계좌: " + ACCT + " " + HOLDER, last_line(page))

        # ---------- 지우기 ----------
        page.click("#payClear")
        page.wait_for_timeout(200)
        ok("지우기 → 입력칸 비움", page.input_value("#payAcct") == "" and page.input_value("#payHolder") == "",
           [page.input_value("#payAcct"), page.input_value("#payHolder")])
        ok("지우기 → 안내 문구", last_line(page) == "🏦 입금 계좌: (계좌번호를 넣어 주세요)", last_line(page))
        ok("지우면 저장값도 비움",
           page.evaluate("() => localStorage.getItem('cpick.payAcct')") == ""
           and page.evaluate("() => localStorage.getItem('cpick.payHolder')") == "",
           page.evaluate("() => [localStorage.getItem('cpick.payAcct'), localStorage.getItem('cpick.payHolder')]"))

        # 예금주만 넣은 경우
        page.fill("#payHolder", HOLDER)
        page.wait_for_timeout(120)
        ok("예금주만 있으면 계좌번호 없이 깔끔히", last_line(page) == "🏦 입금 계좌: " + HOLDER, last_line(page))
        page.fill("#payAcct", ACCT)
        page.fill("#payHolder", "")
        page.wait_for_timeout(150)
        ok("계좌번호만 있으면 뒤 공백 없음", last_line(page) == "🏦 입금 계좌: " + ACCT, repr(last_line(page)))

        # 직접 고친 문구를 복사
        page.fill("#payAcct", ACCT)
        page.wait_for_timeout(100)
        edited = page.input_value("#copyText") + "\n(문구는 자유롭게 고칠 수 있어요)"
        page.fill("#copyText", edited)
        page.click("#copyOk")
        page.wait_for_timeout(200)
        ok("문구를 직접 고쳐도 그대로 복사", page.evaluate("() => navigator.clipboard.readText()") == edited)

        # ---------- 390px 레이아웃 ----------
        fit = page.evaluate("""() => { const s = document.querySelector('#maskCopy .sheet');
            const seg = document.querySelector('#payMode');
            return {sheet: [s.scrollWidth, s.clientWidth], seg: [seg.scrollWidth, seg.clientWidth],
                    btns: Array.from(seg.querySelectorAll('button')).map(b => [b.scrollWidth, b.clientWidth]),
                    bodyScroll: [document.documentElement.scrollWidth, document.documentElement.clientWidth]}; }""")
        ok("390px: 모달 가로 넘침 없음", fit["sheet"][0] <= fit["sheet"][1] + 1, fit["sheet"])
        ok("390px: 선택 버튼 2개 잘림 없음", all(b[0] <= b[1] + 1 for b in fit["btns"]), fit["btns"])
        page.click("#copyClose")
        page.wait_for_timeout(150)

        # ---------- 개인정보가 시트로 가지 않는지 ----------
        grid_txt = json.dumps(page.evaluate("() => window.__sheetGrid"), ensure_ascii=False)
        ok("계좌·예금주가 구글 시트 데이터에 없음", ACCT not in grid_txt and HOLDER not in grid_txt,
           grid_txt[:200])

        # 감춰 둔 계좌가 지난 모임 카드에도 나오지 않는지(카드 본문에는 송금 안내 없음)
        ok("모임 카드 본문에 계좌번호 노출 없음", ACCT not in page.inner_text("#list"),
           page.inner_text("#list")[:200])

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
