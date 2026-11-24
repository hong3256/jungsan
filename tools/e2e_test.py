#!/usr/bin/env python3
"""모바일(390px)·데스크톱 화면에서 진홍이가 만든 참석앱(번개게임·번개회식) 전체 동작 검증.

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
        ctx.add_init_script("(() => { const fn = " + MOCK + "; fn(" + json.dumps(code) + "); })()")

        page = ctx.new_page()
        page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: console_errors.append("pageerror: " + str(e)))
        page.on("dialog", lambda d: d.accept())
        page.goto(url)
        page.wait_for_timeout(600)

        # ---------- 기본 ----------
        ok("페이지 제목 = 진홍이가 만든 참석앱", page.title() == "진홍이가 만든 참석앱", page.title())
        ok("상단 브랜드 제목 = 진홍이가 만든 참석앱", page.inner_text(".brand").strip() == "🏓 진홍이가 만든 참석앱",
           page.inner_text(".brand"))
        brandfit = page.evaluate("""() => { const b = document.querySelector('.brand'); const h = document.querySelector('.top-row');
            return {brand: [b.scrollWidth, b.clientWidth], row: [h.scrollWidth, h.clientWidth]}; }""")
        ok("390px 화면에서 제목이 잘리지 않음", brandfit["brand"][0] <= brandfit["brand"][1] + 1
           and brandfit["row"][0] <= brandfit["row"][1] + 1, brandfit)
        manifest = page.evaluate("""() => fetch('manifest.json').then(r => r.json())""")
        ok("홈화면 이름(manifest name/short_name) = 진홍이가 만든 참석앱",
           manifest.get("name") == "진홍이가 만든 참석앱" and manifest.get("short_name") == "진홍이가 만든 참석앱", manifest)
        ok("실시간 배지 🟢", "실시간" in page.inner_text("#syncBadge"), page.inner_text("#syncBadge"))
        ok("모임 없음 안내", "아직 모임이 없어요" in page.inner_text("#list"))
        tabs = page.inner_text("#tabs")
        ok("탭 명칭 — 번개게임 / 번개회식 / 전체",
           all(k in tabs for k in ["번개게임", "번개회식", "전체"]), tabs)
        ok("탭에 옛 명칭(매일 정기·번개 모임) 없음",
           "매일 정기" not in tabs and "번개 모임" not in tabs and "정기 " not in tabs, tabs)
        boxes = page.evaluate("""() => Array.from(document.querySelectorAll('#tabs .tab')).map(b => {
            const r = b.getBoundingClientRect();
            return {left: Math.round(r.left), right: Math.round(r.right), w: Math.round(r.width),
                    scrollW: b.scrollWidth, clientW: b.clientWidth, text: b.innerText.replace(/\\n/g, ' ')};
        })""")
        ok("390px 화면에서 탭 3개가 잘리지 않음",
           len(boxes) == 3 and all(b["right"] <= 390 and b["scrollW"] <= b["clientW"] + 1 for b in boxes), boxes)
        page.screenshot(path=os.path.join(SHOTS, "cpick-att-mobile-empty.png"))

        # ---------- 계산 함수 ----------
        calc = page.evaluate("""() => ({
          a: window.cpickCore.splitFee(50000, 7, 10),
          b: window.cpickCore.splitFee(30000, 7, 10),
          c: window.cpickCore.splitFee(30000, 0, 10),
          d: window.cpickCore.splitFee(1000, 3, 10),
          e: window.cpickCore.splitFee(0, 5, 10),
          labels: [window.cpickCore.typeLabel('정기'), window.cpickCore.typeLabel('번개')],
          legacy: [window.cpickCore.displayTitle({type: '정기', title: '정기 모임'}),
                   window.cpickCore.displayTitle({type: '번개', title: '번개 모임'}),
                   window.cpickCore.displayTitle({type: '번개', title: '삼겹살'})],
          kakao: [window.cpickCore.kakaoText({type: '정기', title: '정기 모임', date: '2026-11-24', time: '19:00', fee: 30000,
                    votes: [{name: '김민수', status: '참석'}]}, 10),
                  window.cpickCore.kakaoText({type: '번개', title: '번개 모임', date: '2026-11-24', time: '19:00', fee: 30000,
                    votes: [{name: '김민수', status: '참석'}]}, 10)]
        })""")
        ok("50,000÷7 → 7,140원 · 자투리 20원",
           calc["a"]["per"] == 7140 and calc["a"]["remainder"] == 20 and calc["a"]["total"] == 49980, calc["a"])
        ok("30,000÷7 → 4,280원 · 자투리 40원",
           calc["b"]["per"] == 4280 and calc["b"]["remainder"] == 40 and calc["b"]["total"] == 29960, calc["b"])
        ok("참석 0명 → 0원", calc["c"]["per"] == 0 and calc["c"]["remainder"] == 0, calc["c"])
        ok("1,000÷3 → 330원 (10원 절사)", calc["d"]["per"] == 330 and calc["d"]["remainder"] == 10, calc["d"])
        ok("0원 → 0원", calc["e"]["per"] == 0, calc["e"])
        ok("구분 명칭 = 번개게임 / 번개회식", calc["labels"] == ["번개게임", "번개회식"], calc["labels"])
        ok("예전 기본 제목도 새 명칭으로 표시", calc["legacy"] == ["번개게임", "번개회식", "삼겹살"], calc["legacy"])
        ok("카톡 문구 머리 — 번개게임 정산 / 번개회식 정산",
           calc["kakao"][0].split("\n")[0] == "🏓 C-PICK 번개게임 정산"
           and calc["kakao"][1].split("\n")[0] == "🍻 C-PICK 번개회식 정산", [x.split("\n")[0] for x in calc["kakao"]])

        # ---------- 번개게임 만들기 (0원으로 만들고 나중에 금액) ----------
        page.click("#btnNew")
        page.wait_for_selector("#maskEvent.on")
        ok("새 모임 기본 구분 = 번개게임", "번개게임" in page.inner_text("#evType .on"), page.inner_text("#evType .on"))
        ok("번개게임이어도 총 사용료 칸 표시", page.is_visible("#evFee"))
        ok("빠른 금액 버튼 4개", page.locator("#evFeeChips button").count() == 4,
           page.locator("#evFeeChips button").count())
        ok("제목 안내 (비우면 '번개게임')", "번개게임" in page.inner_text("#evTitleLabel"), page.inner_text("#evTitleLabel"))
        page.click('#evType button[data-type="번개"]')
        page.wait_for_timeout(120)
        ok("번개회식으로 바꿔도 사용료 칸 유지", page.is_visible("#evFee"))
        ok("번개회식 제목 안내 (비우면 '번개회식')", "번개회식" in page.inner_text("#evTitleLabel"),
           page.inner_text("#evTitleLabel"))
        page.click('#evType button[data-type="정기"]')
        page.wait_for_timeout(120)
        page.fill("#evPlace", "송암 에어돔 1번코트")
        page.fill("#evTitle", "화요일 번개게임")
        ok("처음 금액은 비어 있음(0원)", page.input_value("#evFee") in ("", "0"), page.input_value("#evFee"))
        page.click("#evSave")
        page.wait_for_selector(".card")
        page.wait_for_timeout(300)
        card = card_with(page, "화요일 번개게임")
        ok("번개게임 카드 생성", card is not None, page.inner_text("#list")[:300])
        ok("번개게임 배지 표시", "번개게임" in card.locator(".tag").inner_text() and "🏓" in card.locator(".tag").inner_text(),
           card.locator(".tag").inner_text())
        ok("번개게임 카드에 총 사용료·저장·카톡 버튼",
           card.locator(".fee-input").count() == 1 and card.locator(".fee-save").count() == 1
           and card.locator(".copy-btn").count() == 1)
        ok("0원이면 1인당 대신 안내", "아직 나눌 수 없어요" in card.inner_text(), card.inner_text()[-260:])
        ok("탭 숫자(번개게임 1)", page.inner_text("#n-정기") == "1", page.inner_text("#n-정기"))
        ok("오늘 모임으로 표시", "오늘" in page.inner_text(".when"), page.inner_text(".when"))
        game_id = page.get_attribute(".card", "data-id")

        # ---------- 원터치 투표 (7명) ----------
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

        names = ["이서연", "박지훈", "최유진", "정다은", "강현우", "윤지호"]
        for n in names:
            page.fill("#myName", n)
            page.click('.card .vote[data-status="참석"]')
            page.wait_for_timeout(260)
        ok("7명 참석", "참석 7" in page.inner_text(".counts"), page.inner_text(".counts"))

        # 나중에 금액 입력 → 저장 → 1/N (10원 미만 절사)
        page.fill(".fee-input", "50000")
        page.click(".fee-save")
        page.wait_for_timeout(500)
        per = page.inner_text(".perline")
        ok("번개게임 5만원÷7명 → 1인당 7,140원", "7,140원" in per, per)
        ok("번개게임 자투리 20원 표시", "자투리 20원" in page.inner_text(".feebox"), page.inner_text(".feebox")[:300])
        ok("저장 토스트", "50,000원" in page.inner_text("#toast"), page.inner_text("#toast"))
        grid = page.evaluate("() => window.__sheetGrid")
        ok("시트 모임목록에 사용료 50,000 저장",
           any(r[0] == game_id and str(r[6]) == "50000" for r in grid["모임목록"][1:]),
           [r for r in grid["모임목록"][1:] if r[0] == game_id])
        page.screenshot(path=os.path.join(SHOTS, "cpick-att-mobile-list.png"))

        # ---------- 금액 칸에 치는 동안 자동 새로고침이 값을 지우지 않는지 ----------
        page.fill(".fee-input", "45000")
        page.focus(".fee-input")
        page.wait_for_timeout(4600)
        ok("금액 입력 중 4초 새로고침이 값을 지우지 않음", page.input_value(".fee-input") == "45000",
           page.input_value(".fee-input"))
        page.fill(".fee-input", "50000")
        page.click(".fee-save")
        page.wait_for_timeout(4600)

        # ---------- 번개게임 카톡 정산 ----------
        page.click(".copy-btn")
        page.wait_for_selector("#maskCopy.on")
        txt = page.input_value("#copyText")
        ok("카톡 문구 머리 — 🏓 C-PICK 번개게임 정산", txt.split("\n")[0] == "🏓 C-PICK 번개게임 정산", txt.split("\n")[0])
        ok("카톡 문구 — 제목/총액/참석/1인당/자투리",
           all(k in txt for k in ["화요일 번개게임", "총 사용료 50,000원", "참석 7명",
                                  "1인당 7,140원 (10원 미만 절사)", "자투리 20원", "김민수", "윤지호"]), txt)
        ok("문구에 날짜 표기", "/" in txt and "19:00" in txt, txt.split("\n")[2] if len(txt.split("\n")) > 2 else txt)
        clip = page.evaluate("() => navigator.clipboard.readText()")
        ok("클립보드에 같은 문구", clip.strip() == txt.strip(), clip[:80])
        page.screenshot(path=os.path.join(SHOTS, "cpick-att-mobile-kakao.png"))
        page.click("#copyClose")

        # ---------- 번개회식 (3만원) ----------
        page.click("#btnNew")
        page.click('#evType button[data-type="번개"]')
        page.wait_for_timeout(120)
        page.fill("#evPlace", "스무숲")
        page.fill("#evTitle", "삼겹살 번개회식")
        page.click('#evFeeChips button[data-f="30000"]')
        ok("빠른 금액 칩 → 30000", page.input_value("#evFee") == "30000", page.input_value("#evFee"))
        page.click("#evSave")
        page.wait_for_timeout(450)
        page.click('#tabs button[data-tab="번개"]')
        page.wait_for_timeout(250)
        ok("번개회식 탭에 1건", page.locator(".card").count() == 1, page.locator(".card").count())
        rc = card_with(page, "삼겹살 번개회식")
        ok("번개회식 배지 표시", rc is not None and "번개회식" in rc.locator(".tag").inner_text()
           and "🍻" in rc.locator(".tag").inner_text(), rc.locator(".tag").inner_text() if rc else None)
        ok("번개회식 카드에도 총 사용료·저장·카톡 버튼",
           rc.locator(".fee-input").count() == 1 and rc.locator(".fee-save").count() == 1
           and rc.locator(".copy-btn").count() == 1)
        ok("번개회식 탭 숫자", page.inner_text("#n-번개") == "1", page.inner_text("#n-번개"))

        for n in ["김민수", "이서연"]:
            page.fill("#myName", n)
            page.click('.card .vote[data-status="참석"]')
            page.wait_for_timeout(300)
        ok("번개회식 3만원÷2명 → 1인당 15,000원", "15,000원" in page.inner_text(".perline"),
           page.inner_text(".perline"))
        page.click(".copy-btn")
        page.wait_for_selector("#maskCopy.on")
        txt = page.input_value("#copyText")
        ok("번개회식 카톡 문구 머리 — 🍻 C-PICK 번개회식 정산", txt.split("\n")[0] == "🍻 C-PICK 번개회식 정산",
           txt.split("\n")[0])
        ok("번개회식 문구 내용", "삼겹살 번개회식" in txt and "총 사용료 30,000원" in txt and "1인당 15,000원" in txt, txt)
        page.click("#copyClose")

        # ---------- 전체 탭 ----------
        page.click('#tabs button[data-tab="전체"]')
        page.wait_for_timeout(250)
        whole = page.inner_text("#list")
        ok("전체 탭에 두 모임", "화요일 번개게임" in whole and "삼겹살 번개회식" in whole, whole[:300])
        ok("전체 탭 숫자 2", page.inner_text("#n-전체") == "2", page.inner_text("#n-전체"))
        ok("전체 탭에 옛 명칭 없음", "매일 정기" not in page.inner_text("body") and "⚡ 번개" not in page.inner_text("body"),
           page.inner_text("body")[:400])

        # ---------- 다른 사람(두 번째 화면)이 투표 → 실시간 반영 ----------
        page2 = ctx.new_page()
        page2.on("dialog", lambda d: d.accept())
        page2.goto(base + "/index.html?sync=/mock")
        page2.wait_for_timeout(500)
        page2.fill("#myName", "한지민")
        tgt = card_with(page2, "화요일 번개게임")
        tgt.locator('.vote[data-status="참석"]').click()
        page2.wait_for_timeout(400)
        page.wait_for_timeout(4600)   # 4초 폴링 기다림
        first = card_with(page, "화요일 번개게임")
        ok("다른 사람 투표가 4초 안에 내 화면에 반영", "참석 8" in first.inner_text(), first.inner_text()[:200])
        ok("8명이면 1인당 6,250원(50,000÷8)", "6,250원" in first.inner_text(), first.inner_text()[-200:])
        page2.close()

        # ---------- 관리자 PIN ----------
        ok("관리자가 아니면 모두 지우기 버튼 없음", page.locator("#btnWipeAll").count() == 0)
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
        ok("관리자만 '모두 지우기' 버튼 표시", page.is_visible("#btnWipeAll") and "모두 지우기" in page.inner_text("#btnWipeAll"),
           page.inner_text(".admintools"))

        # 마감/재개
        first = card_with(page, "화요일 번개게임")
        first.locator("button[data-close]").click()
        page.wait_for_timeout(450)
        first = card_with(page, "화요일 번개게임")
        ok("마감 표시", "마감" in first.inner_text(), first.inner_text()[:160])
        ok("마감되면 투표 버튼 잠김", first.locator('.vote[data-status="참석"]').is_disabled())
        first.locator("button[data-close]").click()
        page.wait_for_timeout(450)
        first = card_with(page, "화요일 번개게임")
        ok("재개 → 투표 버튼 다시 활성", not first.locator('.vote[data-status="참석"]').is_disabled())

        # 수정
        first.locator("button[data-edit]").click()
        page.wait_for_selector("#maskEvent.on")
        ok("수정 창에 기존 값", page.input_value("#evPlace") == "송암 에어돔 1번코트", page.input_value("#evPlace"))
        ok("수정 창 금액도 채워짐", page.input_value("#evFee") == "50000", page.input_value("#evFee"))
        page.fill("#evPlace", "송암 에어돔 2번코트")
        page.click("#evSave")
        page.wait_for_timeout(450)
        ok("장소 수정 반영", "송암 에어돔 2번코트" in page.inner_text("#list"), page.inner_text("#list")[:200])

        # ---------- 지난 모임 정리 ----------
        page.click("#btnNew")
        page.fill("#evDate", "2020-11-20")
        page.fill("#evTitle", "지난주 번개게임")
        page.click("#evSave")
        page.wait_for_timeout(500)
        ok("관리자 도구에 지난 모임 정리 버튼", "지난 모임" in page.inner_text(".admintools"), page.inner_text(".admintools"))
        page.click("#btnCleanPast")
        page.wait_for_timeout(600)
        ok("지난 모임 정리 실행", "1개 지난 모임을 정리했어요" in page.inner_text("#toast"), page.inner_text("#toast"))
        page.click('#tabs button[data-tab="전체"]')
        page.wait_for_timeout(250)
        ok("지난 모임 사라짐", "지난주 번개게임" not in page.inner_text("#list"))

        # ---------- 삭제 ----------
        page.click("#btnNew")
        page.fill("#evTitle", "지울 모임")
        page.click("#evSave")
        page.wait_for_timeout(500)
        gone = card_with(page, "지울 모임")
        gone.locator("button[data-del]").click()
        page.wait_for_timeout(700)
        ok("삭제 확인 후 목록에서 사라짐", "지울 모임" not in page.inner_text("#list"), page.inner_text("#list")[:200])
        grid = page.evaluate("() => window.__sheetGrid")
        ok("시트 참석기록에 고아 행 없음",
           all(any(r[0] == v[0] for r in grid["모임목록"][1:]) for v in grid["참석기록"][1:]),
           grid["참석기록"][1:])

        # ---------- 모두 지우기 (관리자 전용) ----------
        before = page.locator(".card").count()
        ok("모두 지우기 전 모임 있음", before >= 2, before)
        page.click("#btnWipeAll")
        page.wait_for_timeout(1800)
        ok("모두 지우기 → 목록 비음", page.locator(".card").count() == 0 and "아직 모임이 없어요" in page.inner_text("#list"),
           page.inner_text("#list")[:200])
        ok("모두 지우기 토스트", "모든 모임 " + str(before) + "개를 지웠어요" in page.inner_text("#toast"),
           page.inner_text("#toast"))
        grid = page.evaluate("() => window.__sheetGrid")
        ok("시트 모임목록도 비움", len([r for r in grid["모임목록"][1:] if any(str(v).strip() for v in r)]) == 0,
           grid["모임목록"])
        ok("시트 참석기록도 비움", len([r for r in grid["참석기록"][1:] if any(str(v).strip() for v in r)]) == 0,
           grid["참석기록"])
        ok("모두 지운 뒤에는 버튼 숨김", page.locator("#btnWipeAll").count() == 0)

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
        dpage.fill("#evTitle", "데스크톱 번개회식")
        dpage.fill("#evPlace", "송암 2번코트")
        dpage.fill("#evFee", "30000")
        dpage.click("#evSave")
        dpage.wait_for_timeout(400)
        dpage.click('#tabs button[data-tab="번개"]')
        dpage.fill("#myName", "김민수")
        dpage.click('.card .vote[data-status="참석"]')
        dpage.wait_for_timeout(300)
        ok("데스크톱: 로컬 모드에서도 모임 생성·투표", "데스크톱 번개회식" in dpage.inner_text("#list")
           and "참석 1" in dpage.inner_text(".counts"), dpage.inner_text("#list")[:200])
        ok("데스크톱: 한 명이면 1인당 30,000원", "30,000원" in dpage.inner_text(".perline"), dpage.inner_text(".perline"))
        dpage.click("#btnNew")
        dpage.click('#evType button[data-type="정기"]')
        dpage.fill("#evTitle", "데스크톱 번개게임")
        dpage.fill("#evFee", "20000")
        dpage.click("#evSave")
        dpage.wait_for_timeout(400)
        dpage.click('#tabs button[data-tab="정기"]')
        dpage.wait_for_timeout(200)
        dgame = card_with(dpage, "데스크톱 번개게임")
        ok("데스크톱: 번개게임(정기)도 사용료 칸·1/N", dgame is not None and dgame.locator(".fee-input").count() == 1
           and dgame.locator(".fee-input").input_value() == "20000",
           dgame.inner_text()[-200:] if dgame else None)
        dgame.locator('.vote[data-status="참석"]').click()
        dpage.wait_for_timeout(400)
        dgame = card_with(dpage, "데스크톱 번개게임")
        ok("데스크톱: 번개게임 1명 참석 → 1인당 20,000원", "20,000원" in dgame.inner_text(),
           dgame.inner_text()[-200:] if dgame else None)
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
