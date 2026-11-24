#!/usr/bin/env python3
"""모바일(390px)·데스크톱 화면에서 C-PICK 참석·정산 앱 전체 동작 검증.

- 앱 화면(index.html)은 실제 파일을 그대로 띄우고,
- /mock 요청은 downloads/cpick-attendance-apps-script.txt 의 진짜 Apps Script 코드를
  시트 목(그리드)과 함께 실행해 응답한다(브라우저 fetch 가로채기).
- 시트 그리드는 localStorage 에 저장해 두 페이지(=두 사람)가 같은 시트를 본다.
"""
import functools
import http.server
import json
import os
import socketserver
import sys
import threading

from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GS = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(HERE), "downloads", "cpick-attendance-apps-script.txt")
SHOTS = os.path.join(os.path.dirname(HERE), "downloads")

MOCK = r"""
(code) => {
  const HEADERS = {
    '모임목록': ['모임ID','구분','날짜','시간','장소','제목/메모','총사용료','상태','생성시각'],
    '참석기록': ['모임ID','이름','상태','메모','갱신시각'],
    '설정': [['관리자PIN','0629'],['절사단위','10']]
  };
  const GRID = {};
  Object.keys(HEADERS).forEach(function (k) {
    const h = HEADERS[k];
    GRID[k] = (Array.isArray(h[0]) ? h.map(r => r.slice()) : [h.slice()]);
  });
  const KEY = '__cpickMockGrid';
  try {
    const saved = JSON.parse(localStorage.getItem(KEY) || 'null');
    if (saved) Object.keys(saved).forEach(k => { if (GRID[k]) GRID[k] = saved[k]; });
  } catch (e) {}
  function persist() { try { localStorage.setItem(KEY, JSON.stringify(GRID)); } catch (e) {} }
  function reload() {
    try {
      const saved = JSON.parse(localStorage.getItem(KEY) || 'null');
      if (saved) Object.keys(saved).forEach(k => { if (GRID[k]) GRID[k] = saved[k]; });
    } catch (e) {}
  }
  function isEmpty(v) { return v === '' || v === null || v === undefined; }
  function lastRow(grid) {
    let last = 0;
    for (let i = 0; i < grid.length; i++) if (grid[i].some(v => !isEmpty(v))) last = i + 1;
    return last;
  }
  function makeSheet(name) {
    const grid = GRID[name];
    return {
      getName() { return name; },
      getLastRow() { return lastRow(grid); },
      getRange(row, col, numRows, numCols) {
        const nr = numRows === undefined ? 1 : numRows;
        const nc = numCols === undefined ? 1 : numCols;
        return {
          getValue() { return (grid[row - 1] || [])[col - 1] === undefined ? '' : (grid[row - 1] || [])[col - 1]; },
          getValues() {
            const out = [];
            for (let r = 0; r < nr; r++) {
              const src = grid[row - 1 + r] || [];
              const rr = [];
              for (let c = 0; c < nc; c++) rr.push(src[col - 1 + c] === undefined ? '' : src[col - 1 + c]);
              out.push(rr);
            }
            return out;
          },
          setValue(v) {
            while (grid.length < row) grid.push([]);
            const t = grid[row - 1];
            while (t.length < col) t.push('');
            t[col - 1] = v;
          },
          setValues(vals) {
            for (let r = 0; r < vals.length; r++) {
              while (grid.length < row + r) grid.push([]);
              const t = grid[row - 1 + r];
              for (let c = 0; c < vals[r].length; c++) {
                while (t.length < col + c) t.push('');
                t[col - 1 + c] = vals[r][c];
              }
            }
          }
        };
      },
      appendRow(vals) {
        const at = lastRow(grid) + 1;
        while (grid.length < at) grid.push([]);
        grid[at - 1] = vals.slice();
      },
      deleteRow(n) { if (n >= 1 && n <= grid.length) grid.splice(n - 1, 1); }
    };
  }
  const ssObj = {
    getName() { return 'C-PICK 참석·번개 관리'; },
    getSheets() { return Object.keys(GRID).map(makeSheet); },
    getSheetByName(n) { return GRID[n] ? makeSheet(n) : null; }
  };
  const SpreadsheetApp = { openById() { return ssObj; }, getActiveSpreadsheet() { return ssObj; }, flush() {} };
  const ContentService = {
    MimeType: { JSON: 'application/json' },
    createTextOutput(text) {
      let mime = 'text/plain';
      return { getContent() { return text; }, getMimeType() { return mime; }, setMimeType(m) { mime = m; return this; } };
    }
  };
  function p2(n) { return (n < 10 ? '0' : '') + n; }
  const Utilities = {
    formatDate(d, tz, fmt) {
      return String(fmt).replace(/yyyy/g, String(d.getFullYear())).replace(/MM/g, p2(d.getMonth() + 1))
        .replace(/dd/g, p2(d.getDate())).replace(/HH/g, p2(d.getHours()))
        .replace(/mm/g, p2(d.getMinutes())).replace(/ss/g, p2(d.getSeconds()));
    }
  };
  const LockService = { getScriptLock() { return { waitLock() { return true; }, releaseLock() {} }; } };
  const Logger = { log() {} };
  const api = new Function('SpreadsheetApp', 'ContentService', 'Utilities', 'LockService', 'Logger',
    code + '\nreturn { doGet: doGet, doPost: doPost };')(SpreadsheetApp, ContentService, Utilities, LockService, Logger);

  window.__sheetGrid = GRID;
  window.__offline = false;
  window.__mockCount = 0;
  const realFetch = window.fetch.bind(window);
  window.fetch = function (input, init) {
    const url = typeof input === 'string' ? input : (input && input.url) || '';
    if (url.indexOf('/mock') < 0) return realFetch(input, init);
    const method = ((init && init.method) || 'GET').toUpperCase();
    return new Promise(function (resolve, reject) {
      setTimeout(function () {
        if (window.__offline) { reject(new TypeError('Failed to fetch')); return; }
        let payload;
        reload();
        try {
          if (method === 'POST') {
            payload = api.doPost({ postData: { contents: (init && init.body) || '{}' } }).getContent();
          } else {
            const q = url.split('?')[1] || '';
            const params = {};
            q.split('&').forEach(function (p) {
              const i = p.indexOf('=');
              if (i > 0) params[decodeURIComponent(p.slice(0, i))] = decodeURIComponent(p.slice(i + 1));
            });
            payload = api.doGet({ parameter: params }).getContent();
          }
        } catch (err) { reject(err); return; }
        persist();
        window.__mockCount++;
        resolve(new Response(payload, { status: 200, headers: { 'Content-Type': 'application/json' } }));
      }, 40);
    });
  };
  return true;
}
"""


def serve(directory):
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=directory)

    class Quiet(handler.func):
        def log_message(self, *a):
            pass

    httpd = socketserver.ThreadingTCPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=directory))
    httpd.daemon_threads = True
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, httpd.server_address[1]


def main():
    code = open(GS, encoding="utf-8").read()
    httpd, port = serve(HERE)
    base = f"http://127.0.0.1:{port}"
    url = base + "/index.html?sync=/mock"

    results = []

    def ok(name, cond, detail=None):
        results.append((bool(cond), name, detail))
        print(("통과  " if cond else "실패  ") + name + ("" if cond or detail is None else
              " :: " + json.dumps(detail, ensure_ascii=False)[:400]))

    console_errors = []

    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2,
                                  is_mobile=True, has_touch=True)
        ctx.grant_permissions(["clipboard-read", "clipboard-write"], origin=base)
        ctx.add_init_script("(() => { const fn = " + MOCK + "; fn(" + json.dumps(code) + "); })()")

        page = ctx.new_page()
        page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: console_errors.append("pageerror: " + str(e)))
        page.on("dialog", lambda d: d.accept())
        page.goto(url)
        page.wait_for_timeout(600)

        # ---------- 기본 ----------
        ok("페이지 제목", page.title() == "C-PICK 참석·정산", page.title())
        ok("실시간 배지 🟢", "실시간" in page.inner_text("#syncBadge"), page.inner_text("#syncBadge"))
        ok("모임 없음 안내", "아직 모임이 없어요" in page.inner_text("#list"))
        page.screenshot(path=os.path.join(SHOTS, "cpick-att-mobile-empty.png"))

        # ---------- 계산 함수 ----------
        calc = page.evaluate("""() => ({
          a: window.cpickCore.splitFee(50000, 7, 10),
          b: window.cpickCore.splitFee(30000, 7, 10),
          c: window.cpickCore.splitFee(30000, 0, 10),
          d: window.cpickCore.splitFee(1000, 3, 10),
          e: window.cpickCore.splitFee(0, 5, 10)
        })""")
        ok("50,000÷7 → 7,140원 · 자투리 20원",
           calc["a"]["per"] == 7140 and calc["a"]["remainder"] == 20 and calc["a"]["total"] == 49980, calc["a"])
        ok("30,000÷7 → 4,280원 · 자투리 40원",
           calc["b"]["per"] == 4280 and calc["b"]["remainder"] == 40 and calc["b"]["total"] == 29960, calc["b"])
        ok("참석 0명 → 0원", calc["c"]["per"] == 0 and calc["c"]["remainder"] == 0, calc["c"])
        ok("1,000÷3 → 330원 (10원 절사)", calc["d"]["per"] == 330 and calc["d"]["remainder"] == 10, calc["d"])
        ok("0원 → 0원", calc["e"]["per"] == 0, calc["e"])

        # ---------- 정기 모임 만들기 ----------
        page.click("#btnNew")
        page.wait_for_selector("#maskEvent.on")
        ok("새 모임 기본 구분=정기", page.inner_text("#evType .on").find("정기") >= 0, page.inner_text("#evType .on"))
        ok("번개가 아니면 사용료 칸 숨김", not page.is_visible("#evFee"))
        page.fill("#evPlace", "송암 에어돔 1번코트")
        page.fill("#evTitle", "11월 4주 정기모임")
        page.click("#evSave")
        page.wait_for_selector(".card")
        card = page.inner_text(".card")
        ok("정기 모임 카드 생성", "11월 4주 정기모임" in card and "송암 에어돔" in card, card[:300])
        ok("오늘 모임으로 표시", "오늘" in page.inner_text(".when"), page.inner_text(".when"))
        ok("탭 숫자 반영(정기 1)", page.inner_text("#n-정기") == "1", page.inner_text("#n-정기"))

        # ---------- 원터치 투표 ----------
        page.fill("#myName", "김민수")
        page.click('.card .vote[data-status="참석"]')
        page.wait_for_timeout(400)
        ok("참석 1명 반영", "참석 1" in page.inner_text(".counts").replace("\n", " "), page.inner_text(".counts"))
        ok("내 이름 강조 표시", page.locator(".names .me").count() == 1, page.inner_text(".names"))
        ok("참석 버튼 선택 표시", page.locator('.card .vote[data-status="참석"].on').count() == 1)
        ok("이름이 기기에 저장", page.evaluate("() => localStorage.getItem('cpick.myName')") == "김민수")

        page.click('.card .vote[data-status="미정"]')
        page.wait_for_timeout(350)
        ok("미정으로 바꾸면 참석 0·미정 1",
           "참석 0" in page.inner_text(".counts") and "미정 1" in page.inner_text(".counts"), page.inner_text(".counts"))
        page.click('.card .vote[data-status="참석"]')
        page.wait_for_timeout(350)

        # ---------- 번개 모임 (5만원) ----------
        page.click("#btnNew")
        page.click('#evType button[data-type="번개"]')
        page.wait_for_timeout(120)
        ok("번개 선택 시 사용료 칸 표시", page.is_visible("#evFee"))
        page.fill("#evPlace", "스무숲")
        page.fill("#evTitle", "화요일 번개")
        page.click('#evFeeChips button[data-f="50000"]')
        ok("빠른 금액 칩 → 50000", page.input_value("#evFee") == "50000", page.input_value("#evFee"))
        page.click("#evSave")
        page.wait_for_timeout(400)
        page.click('#tabs button[data-tab="번개"]')
        page.wait_for_timeout(200)
        ok("번개 탭에 1건", page.locator(".card").count() == 1, page.locator(".card").count())

        # 7명 참석
        names = ["김민수", "이서연", "박지훈", "최유진", "정다은", "강현우", "윤지호"]
        for n in names:
            page.fill("#myName", n)
            page.click('.card .vote[data-status="참석"]')
            page.wait_for_timeout(260)
        ok("7명 참석", "참석 7" in page.inner_text(".counts"), page.inner_text(".counts"))
        per = page.inner_text(".perline")
        ok("5만원÷7명 → 1인당 7,140원 표시", "7,140원" in per, per)
        ok("자투리 20원 표시", "자투리 20원" in page.inner_text(".feebox"), page.inner_text(".feebox")[:300])

        # ---------- 사용료 수정 → 3만원 ----------
        page.fill(".fee-input", "30000")
        page.click(".fee-save")
        page.wait_for_timeout(450)
        per = page.inner_text(".perline")
        ok("3만원÷7명 → 1인당 4,280원", "4,280원" in per, per)
        ok("3만원 자투리 40원 표시", "자투리 40원" in page.inner_text(".feebox"), page.inner_text(".feebox")[:300])
        page.screenshot(path=os.path.join(SHOTS, "cpick-att-mobile-list.png"))

        # ---------- 카톡 정산 복사 ----------
        page.click(".copy-btn")
        page.wait_for_selector("#maskCopy.on")
        txt = page.input_value("#copyText")
        ok("정산 문구 — 제목/날짜/참석자/총액/1인당",
           all(k in txt for k in ["화요일 번개", "총 사용료 30,000원", "참석 7명", "1인당 4,280원 (10원 미만 절사)",
                                  "자투리 40원", "김민수", "윤지호"]), txt)
        ok("문구에 날짜 표기", "/" in txt and "19:00" in txt, txt.split("\n")[2] if len(txt.split("\n")) > 2 else txt)
        page.screenshot(path=os.path.join(SHOTS, "cpick-att-mobile-kakao.png"))
        clip = page.evaluate("() => navigator.clipboard.readText()")
        ok("클립보드에 같은 문구", clip.strip() == txt.strip(), clip[:80])
        page.click("#copyClose")

        # ---------- 참석 0명 번개 ----------
        page.click("#btnNew")
        page.click('#evType button[data-type="번개"]')
        page.fill("#evTitle", "아직 아무도 없는 번개")
        page.fill("#evFee", "30000")
        page.click("#evSave")
        page.wait_for_timeout(400)
        page.click('#tabs button[data-tab="번개"]')
        page.wait_for_timeout(200)
        zero = [c for c in page.locator(".card").all() if "아직 아무도 없는 번개" in c.inner_text()]
        ok("참석 0명이면 1인당 대신 안내", zero and "아직 나눌 수 없어요" in zero[0].inner_text(), zero[0].inner_text()[-300:] if zero else None)

        # ---------- 다른 사람(두 번째 화면)이 투표 → 실시간 반영 ----------
        page2 = ctx.new_page()
        page2.on("dialog", lambda d: d.accept())
        page2.goto(base + "/index.html?sync=/mock")
        page2.wait_for_timeout(500)
        page2.click('#tabs button[data-tab="번개"]')
        page2.fill("#myName", "한지민")
        tgt = [c for c in page2.locator(".card").all() if "화요일 번개" in c.inner_text()][0]
        tgt.locator('.vote[data-status="참석"]').click()
        page2.wait_for_timeout(400)
        page.wait_for_timeout(4600)   # 4초 폴링 기다림
        first = [c for c in page.locator(".card").all() if "화요일 번개" in c.inner_text()][0]
        ok("다른 사람 투표가 4초 안에 내 화면에 반영", "참석 8" in first.inner_text(), first.inner_text()[:200])
        ok("8명이면 1인당 3,750원(30,000÷8=3,750)", "3,750원" in first.inner_text(), first.inner_text()[-200:])
        page2.close()

        # ---------- 관리자 PIN ----------
        page.click("#btnAdmin")
        page.fill("#pinInput", "0000")
        page.click("#pinOk")
        page.wait_for_timeout(350)
        ok("틀린 PIN → 안내", "PIN이 맞지 않아요" in page.inner_text("#toast"), page.inner_text("#toast"))
        ok("틀린 PIN 이면 관리자 아님", not page.evaluate("() => document.body.classList.contains('admin')"))
        page.fill("#pinInput", "0629")
        page.click("#pinOk")
        page.wait_for_timeout(450)
        ok("PIN 0629 → 관리자 모드", page.evaluate("() => document.body.classList.contains('admin')"))
        ok("관리자 도구 표시", page.is_visible(".admintools"))

        # 마감/재개
        first = [c for c in page.locator(".card").all() if "화요일 번개" in c.inner_text()][0]
        first.locator('button[data-close]').click()
        page.wait_for_timeout(450)
        first = [c for c in page.locator(".card").all() if "화요일 번개" in c.inner_text()][0]
        ok("마감 표시", "마감" in first.inner_text(), first.inner_text()[:160])
        ok("마감되면 투표 버튼 잠김", first.locator('.vote[data-status="참석"]').is_disabled())
        first.locator('button[data-close]').click()
        page.wait_for_timeout(450)
        first = [c for c in page.locator(".card").all() if "화요일 번개" in c.inner_text()][0]
        ok("재개 → 투표 버튼 다시 활성", not first.locator('.vote[data-status="참석"]').is_disabled())

        # 수정
        first.locator('button[data-edit]').click()
        page.wait_for_selector("#maskEvent.on")
        ok("수정 창에 기존 값", page.input_value("#evPlace") == "스무숲", page.input_value("#evPlace"))
        page.fill("#evPlace", "스무숲 2번코트")
        page.click("#evSave")
        page.wait_for_timeout(450)
        ok("장소 수정 반영", "스무숲 2번코트" in page.inner_text("#list"), page.inner_text("#list")[:200])

        # ---------- 지난 모임 정리 ----------
        page.click("#btnNew")
        page.fill("#evDate", "2026-11-20")
        page.fill("#evTitle", "지난주 정기")
        page.click("#evSave")
        page.wait_for_timeout(450)
        ok("관리자 도구에 지난 모임 정리 버튼", "지난 모임" in page.inner_text(".admintools"), page.inner_text(".admintools"))
        page.click("#btnCleanPast")
        page.wait_for_timeout(500)
        ok("지난 모임 정리 실행", "1개 지난 모임을 정리했어요" in page.inner_text("#toast"), page.inner_text("#toast"))
        page.click('#tabs button[data-tab="전체"]')
        page.wait_for_timeout(200)
        ok("지난 모임 사라짐", "지난주 정기" not in page.inner_text("#list"))

        # ---------- 삭제 ----------
        page.click("#btnNew")
        page.fill("#evTitle", "지울 모임")
        page.click("#evSave")
        page.wait_for_timeout(450)
        card = [c for c in page.locator(".card").all() if "지울 모임" in c.inner_text()][0]
        card.locator('button[data-del]').click()
        page.wait_for_timeout(600)
        ok("삭제 확인 후 목록에서 사라짐", "지울 모임" not in page.inner_text("#list"), page.inner_text("#list")[:200])
        grid = page.evaluate("() => window.__sheetGrid")
        ok("시트 참석기록에 고아 행 없음",
           all(any(r[0] == v[0] for r in grid["모임목록"][1:]) for v in grid["참석기록"][1:]),
           grid["참석기록"][1:])

        # ---------- 연결 끊김 표시 ----------
        page.evaluate("() => { window.__offline = true; }")
        page.wait_for_timeout(13500)
        ok("연결 끊기면 🔴 표시", "연결" in page.inner_text("#syncBadge"), page.inner_text("#syncBadge"))
        page.evaluate("() => { window.__offline = false; }")
        page.wait_for_timeout(5000)
        ok("복구되면 🟢 실시간", "실시간" in page.inner_text("#syncBadge"), page.inner_text("#syncBadge"))

        page.screenshot(path=os.path.join(SHOTS, "cpick-att-mobile-admin.png"), full_page=True)

        # ---------- 데스크톱 ----------
        dctx = browser.new_context(viewport={"width": 1280, "height": 860})
        dctx.add_init_script("(() => { const fn = " + MOCK + "; fn(" + json.dumps(code) + "); })()")
        dpage = dctx.new_page()
        dpage.on("console", lambda m: console_errors.append("desktop: " + m.text) if m.type == "error" else None)
        dpage.on("pageerror", lambda e: console_errors.append("desktop pageerror: " + str(e)))
        dpage.on("dialog", lambda d: d.accept())
        dpage.goto(base + "/index.html?local=1")     # 데스크톱은 로컬 모드도 함께 확인
        dpage.wait_for_timeout(500)
        ok("로컬 모드 배지", "이 기기에만 저장" in dpage.inner_text("#syncBadge"), dpage.inner_text("#syncBadge"))
        dpage.click("#btnNew")
        dpage.click('#evType button[data-type="번개"]')
        dpage.fill("#evTitle", "데스크톱 번개")
        dpage.fill("#evPlace", "송암 2번코트")
        dpage.fill("#evFee", "30000")
        dpage.click("#evSave")
        dpage.wait_for_timeout(400)
        dpage.click('#tabs button[data-tab="번개"]')
        dpage.fill("#myName", "김민수")
        dpage.click('.card .vote[data-status="참석"]')
        dpage.wait_for_timeout(300)
        ok("데스크톱: 로컬 모드에서도 모임 생성·투표", "데스크톱 번개" in dpage.inner_text("#list")
           and "참석 1" in dpage.inner_text(".counts"), dpage.inner_text("#list")[:200])
        ok("데스크톱: 한 명이면 1인당 30,000원", "30,000원" in dpage.inner_text(".perline"), dpage.inner_text(".perline"))
        dpage.screenshot(path=os.path.join(SHOTS, "cpick-att-desktop.png"))

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
