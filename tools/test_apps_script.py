#!/usr/bin/env python3
"""downloads/cpick-attendance-apps-script.txt (Code.gs) 동작 검증.

구글 서비스(SpreadsheetApp·ContentService·LockService·Utilities·Logger)를
실제 시트처럼 흉내 낸 메모리 그리드로 바꿔 끼우고, doGet/doPost 의 모든 action 을
실제로 실행해 확인한다. (Node 없이 Playwright 브라우저 JS 엔진 사용)
"""
import json
import os
import sys

from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GS = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(HERE), "downloads", "cpick-attendance-apps-script.txt")

INIT = r"""
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

  function emptyRow(n) { const a = []; for (let i = 0; i < n; i++) a.push(''); return a; }
  function isEmpty(v) { return v === '' || v === null || v === undefined; }
  function sheetLastRow(grid) {
    let last = 0;
    for (let i = 0; i < grid.length; i++) {
      if (grid[i].some(v => !isEmpty(v))) last = i + 1;
    }
    return last;
  }

  function makeSheet(name) {
    const grid = GRID[name];
    return {
      getName() { return name; },
      getLastRow() { return sheetLastRow(grid); },
      getRange(row, col, numRows, numCols) {
        const nr = numRows === undefined ? 1 : numRows;
        const nc = numCols === undefined ? 1 : numCols;
        return {
          getValue() { return (grid[row - 1] || [])[col - 1] === undefined ? '' : (grid[row - 1] || [])[col - 1]; },
          getValues() {
            const outRows = [];
            for (let r = 0; r < nr; r++) {
              const src = grid[row - 1 + r] || [];
              const rr = [];
              for (let c = 0; c < nc; c++) rr.push(src[col - 1 + c] === undefined ? '' : src[col - 1 + c]);
              outRows.push(rr);
            }
            return outRows;
          },
          setValue(v) {
            while (grid.length < row) grid.push([]);
            const target = grid[row - 1];
            while (target.length < col) target.push('');
            target[col - 1] = v;
          },
          setValues(vals) {
            for (let r = 0; r < vals.length; r++) {
              while (grid.length < row + r) grid.push([]);
              const target = grid[row - 1 + r];
              for (let c = 0; c < vals[r].length; c++) {
                while (target.length < col + c) target.push('');
                target[col - 1 + c] = vals[r][c];
              }
            }
          }
        };
      },
      appendRow(vals) {
        const at = sheetLastRow(grid) + 1;
        while (grid.length < at) grid.push([]);
        grid[at - 1] = vals.slice();
      },
      deleteRow(n) {
        if (n >= 1 && n <= grid.length) grid.splice(n - 1, 1);
      }
    };
  }

  const ssObj = {
    getName() { return 'C-PICK 참석·번개 관리'; },
    getSheets() { return Object.keys(GRID).map(makeSheet); },
    getSheetByName(n) { return GRID[n] ? makeSheet(n) : null; }
  };

  const SpreadsheetApp = {
    openById() { return ssObj; },
    getActiveSpreadsheet() { return ssObj; },
    flush() { window.__flushes = (window.__flushes || 0) + 1; }
  };
  const ContentService = {
    MimeType: { JSON: 'application/json' },
    createTextOutput(text) {
      let mime = 'text/plain';
      return {
        getContent() { return text; },
        getMimeType() { return mime; },
        setMimeType(m) { mime = m; return this; }
      };
    }
  };
  function p2(n) { return (n < 10 ? '0' : '') + n; }
  const Utilities = {
    formatDate(d, tz, fmt) {
      return String(fmt)
        .replace(/yyyy/g, String(d.getFullYear()))
        .replace(/MM/g, p2(d.getMonth() + 1))
        .replace(/dd/g, p2(d.getDate()))
        .replace(/HH/g, p2(d.getHours()))
        .replace(/mm/g, p2(d.getMinutes()))
        .replace(/ss/g, p2(d.getSeconds()));
    }
  };
  window.__locks = 0;
  const LockService = {
    getScriptLock() {
      return {
        waitLock() { window.__locks++; return true; },
        releaseLock() { window.__releases = (window.__releases || 0) + 1; },
        tryLock() { window.__locks++; return true; }
      };
    }
  };
  const Logger = { log() {} };

  const api = new Function(
    'SpreadsheetApp', 'ContentService', 'Utilities', 'LockService', 'Logger',
    code + '\nreturn { doGet: doGet, doPost: doPost };'
  )(SpreadsheetApp, ContentService, Utilities, LockService, Logger);

  window.__GRID = GRID;
  window.__doGet = function (params) {
    const o = api.doGet({ parameter: params || {} });
    return { mime: o.getMimeType(), body: JSON.parse(o.getContent()) };
  };
  window.__doPost = function (body) {
    const o = api.doPost({ postData: { contents: typeof body === 'string' ? body : JSON.stringify(body) } });
    return { mime: o.getMimeType(), body: JSON.parse(o.getContent()) };
  };
  return true;
}
"""


def main():
    code = open(GS, encoding="utf-8").read()
    results = []

    def ok(name, cond, detail=None):
        results.append((bool(cond), name, detail))
        line = ("통과  " if cond else "실패  ") + name
        if detail is not None and not cond:
            line += " :: " + json.dumps(detail, ensure_ascii=False)[:600]
        print(line)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_context().new_page()
        page.goto("about:blank")
        page.evaluate(INIT, code)

        G = lambda params={}: page.evaluate("(q) => window.__doGet(q)", params)
        P = lambda body: page.evaluate("(b) => window.__doPost(b)", body)
        grid = lambda tab: page.evaluate("(t) => window.__GRID[t]", tab)

        # ---------- 연결 ----------
        ping = G({"action": "ping"})
        ok("ping: JSON MIME", ping["mime"] == "application/json", ping["mime"])
        ok("ping: ok/pong/pinSet/unit", ping["body"].get("ok") is True and ping["body"].get("pong") is True
           and ping["body"].get("pinSet") is True and ping["body"].get("unit") == 10, ping["body"])

        st = G({"action": "state"})
        ok("state: 빈 시트 → events []", st["body"].get("ok") is True and st["body"].get("events") == [], st["body"])

        ok("알 수 없는 GET action", G({"action": "nope"})["body"].get("error") == "UNKNOWN_ACTION")
        ok("깨진 JSON → BAD_JSON", P("{not json")["body"].get("error") == "BAD_JSON")

        # ---------- 모임 만들기 ----------
        r1 = P({"action": "createEvent", "type": "정기", "date": "2026-11-24", "time": "19:00",
                "place": "송암 에어돔 1번코트"})
        ok("정기 모임 생성 ok", r1["body"].get("ok") is True, r1["body"])
        ok("정기 기본 제목 '정기 모임'", r1["body"]["events"][0]["title"] == "정기 모임", r1["body"]["events"][0])
        id1 = r1["body"]["eventId"]
        ok("모임ID 형식(R로 시작)", id1.startswith("R20261124-1900-"), id1)

        r2 = P({"action": "createEvent", "type": "번개", "date": "2026-11-25", "time": "18:30",
                "place": "스무숲", "title": "저녁 번개", "fee": 30000})
        id2 = r2["body"]["eventId"]
        ok("번개 모임 생성 + 사용료", r2["body"]["events"][1]["fee"] == 30000
           and r2["body"]["events"][1]["type"] == "번개", r2["body"]["events"][1])
        ok("번개ID 형식(B로 시작)", id2.startswith("B20261125-1830-"), id2)
        ok("생성 뒤 최신 상태 함께 반환(2건)", len(r2["body"]["events"]) == 2, len(r2["body"]["events"]))

        ok("잘못된 구분 → BAD_TYPE",
           P({"action": "createEvent", "type": "기타", "date": "2026-11-24", "time": "10:00"})["body"].get("error") == "BAD_TYPE")
        ok("잘못된 날짜 → BAD_DATE",
           P({"action": "createEvent", "type": "정기", "date": "2026-13-45", "time": "10:00"})["body"].get("error") == "BAD_DATE")
        ok("잘못된 시간 → BAD_TIME",
           P({"action": "createEvent", "type": "정기", "date": "2026-11-24", "time": "25:99"})["body"].get("error") == "BAD_TIME")
        ok("금액 문자열 '30,000원' → 30000",
           P({"action": "createEvent", "type": "번개", "date": "2026-11-26", "time": "19:00",
              "title": "금액문자", "fee": "30,000원"})["body"]["events"][-1]["fee"] == 30000)

        # ---------- 투표 ----------
        v1 = P({"action": "vote", "eventId": id2, "name": "이진홍", "status": "참석"})
        ok("투표 참석 ok", v1["body"].get("ok") is True, v1["body"].get("error"))
        votes = v1["body"]["events"][1]["votes"]
        ok("참석 1명 기록", len(votes) == 1 and votes[0]["status"] == "참석", votes)

        v2 = P({"action": "vote", "eventId": id2, "name": "이진홍", "status": "미정"})
        votes = v2["body"]["events"][1]["votes"]
        ok("같은 사람 재투표 → 한 줄만 갱신", len(votes) == 1 and votes[0]["status"] == "미정", votes)

        for nm in ["조덕기", "황병열", "이형준", "정상순", "장익준", "윤경석"]:
            last = P({"action": "vote", "eventId": id2, "name": nm, "status": "참석"})
        votes = last["body"]["events"][1]["votes"]
        ok("다중 사용자 투표 7명", len(votes) == 7, [x["name"] for x in votes])
        attend = [x for x in votes if x["status"] == "참석"]
        ok("참석 6명(1명 미정)", len(attend) == 6, len(attend))

        ok("없는 모임 투표 → NOT_FOUND",
           P({"action": "vote", "eventId": "NOPE", "name": "이진홍", "status": "참석"})["body"].get("error") == "NOT_FOUND")
        ok("빈 이름 → BAD_NAME",
           P({"action": "vote", "eventId": id2, "name": "  ", "status": "참석"})["body"].get("error") == "BAD_NAME")
        ok("잘못된 상태 → BAD_STATUS",
           P({"action": "vote", "eventId": id2, "name": "이진홍", "status": "출석"})["body"].get("error") == "BAD_STATUS")

        long_name = "가" * 30
        ln = P({"action": "vote", "eventId": id2, "name": long_name, "status": "참석"})
        stored = [x["name"] for x in ln["body"]["events"][1]["votes"] if x["name"] == "가" * 20]
        ok("긴 이름 20자로 자름", len(stored) == 1, [x["name"] for x in ln["body"]["events"][1]["votes"]])

        inj = P({"action": "vote", "eventId": id1, "name": "<b>태그</b>\n줄바꿈", "status": "참석"})
        ok("이름의 태그·줄바꿈은 글자 그대로 저장", inj["body"]["events"][0]["votes"][0]["name"] == "<b>태그</b> 줄바꿈",
           inj["body"]["events"][0]["votes"][0]["name"])

        # ---------- 사용료 ----------
        f1 = P({"action": "updateFee", "eventId": id2, "fee": 50000})
        ok("사용료 수정(누구나) 50000", f1["body"]["events"][1]["fee"] == 50000, f1["body"].get("error"))
        ok("사용료 수정 시 참석 기록 유지", len(f1["body"]["events"][1]["votes"]) == 8, len(f1["body"]["events"][1]["votes"]))
        ok("없는 모임 사용료 → NOT_FOUND",
           P({"action": "updateFee", "eventId": "NOPE", "fee": 1000})["body"].get("error") == "NOT_FOUND")

        # ---------- PIN ----------
        ok("틀린 PIN → PIN_MISMATCH", P({"action": "verifyPin", "pin": "0000"})["body"].get("error") == "PIN_MISMATCH")
        ok("맞는 PIN 0629 → admin", P({"action": "verifyPin", "pin": "0629"})["body"].get("admin") is True)
        ok("숫자 PIN 629 도 통과", P({"action": "verifyPin", "pin": 629})["body"].get("ok") is True)
        ok("PIN 없이 마감 → 거부",
           P({"action": "toggleClose", "eventId": id2})["body"].get("error") == "PIN_MISMATCH")
        ok("틀린 PIN 삭제 → 거부",
           P({"action": "deleteEvent", "eventId": id2, "pin": "1111"})["body"].get("error") == "PIN_MISMATCH")
        ok("틀린 PIN 삭제 뒤 모임 그대로",
           len(G({"action": "state"})["body"]["events"]) == 3, len(G({"action": "state"})["body"]["events"]))

        # ---------- 관리자: 마감/재개/수정 ----------
        c1 = P({"action": "toggleClose", "eventId": id2, "pin": "0629"})
        ok("마감 처리", c1["body"]["events"][1]["status"] == "마감", c1["body"].get("error"))
        closedVote = P({"action": "vote", "eventId": id2, "name": "새사람", "status": "참석"})
        ok("마감된 모임에는 투표 거부(EVENT_CLOSED)", closedVote["body"].get("error") == "EVENT_CLOSED", closedVote["body"])
        c2 = P({"action": "toggleClose", "eventId": id2, "pin": "0629"})
        ok("재개 처리", c2["body"]["events"][1]["status"] == "진행중", c2["body"].get("error"))
        reopened = P({"action": "vote", "eventId": id2, "name": "새사람", "status": "참석"})
        ok("재개하면 다시 투표 가능", reopened["body"].get("ok") is True, reopened["body"].get("error"))

        e1 = P({"action": "updateEvent", "eventId": id2, "place": "송암 2번코트", "pin": "0629"})
        ok("관리자 모임 정보 수정", e1["body"]["events"][1]["place"] == "송암 2번코트", e1["body"].get("error"))
        ok("수정 시 나머지 값 유지(날짜·금액)",
           e1["body"]["events"][1]["date"] == "2026-11-25" and e1["body"]["events"][1]["fee"] == 50000,
           e1["body"]["events"][1])

        # ---------- 관리자: 삭제 ----------
        d0 = P({"action": "deleteEvent", "eventId": id1, "pin": "0629"})
        ok("모임 삭제 ok", d0["body"].get("ok") is True and len(d0["body"]["events"]) == 2, d0["body"].get("error"))
        ok("삭제한 모임의 참석기록도 사라짐",
           all(v[0] != id1 for v in grid("참석기록")[1:]), grid("참석기록")[1:])
        ok("다른 모임 참석기록은 유지", any(v[0] == id2 for v in grid("참석기록")[1:]))

        # ---------- 지난 모임 정리 ----------
        P({"action": "createEvent", "type": "정기", "date": "2020-01-01", "time": "10:00", "title": "지난 모임"})
        before = G({"action": "state"})["body"]["events"]
        dp = P({"action": "deletePast", "pin": "0629"})
        after = dp["body"]["events"] if "events" in dp["body"] else G({"action": "state"})["body"]["events"]
        ok("지난 모임 정리: 1건 삭제", dp["body"].get("deleted") == 1, dp["body"])
        ok("지난 모임 정리 후 미래 모임 유지",
           sorted([e["date"] for e in after]) == sorted([e["date"] for e in before if e["date"] >= "2026-01-01"]),
           [e["date"] for e in after])

        # ---------- 시트 값 형태 방어 ----------
        page.evaluate("""() => {
          const g = window.__GRID['모임목록'];
          g[1][2] = new Date(2026, 11, 3);   // 날짜 셀이 Date 로 바뀐 경우
          g[1][3] = new Date(1970, 0, 1, 20, 5); // 시간 셀
        }""")
        st = G({"action": "state"})["body"]
        ok("날짜 Date 셀 → YYYY-MM-DD", st["events"][0]["date"] == "2026-12-03", st["events"][0]["date"])
        ok("시간 Date 셀 → HH:mm", st["events"][0]["time"] == "20:05", st["events"][0]["time"])

        # ---------- 설정 시트의 PIN 변경이 바로 반영 ----------
        page.evaluate("""() => { window.__GRID['설정'][0][1] = '1234'; }""")
        ok("시트에서 PIN 바꾸면 옛 PIN 거부",
           P({"action": "verifyPin", "pin": "0629"})["body"].get("error") == "PIN_MISMATCH")
        ok("시트에서 PIN 바꾸면 새 PIN 통과",
           P({"action": "verifyPin", "pin": "1234"})["body"].get("ok") is True)
        page.evaluate("""() => { window.__GRID['설정'][0][1] = ''; }""")
        ok("설정에 PIN이 없으면 NO_PIN",
           P({"action": "verifyPin", "pin": "1234"})["body"].get("error") == "NO_PIN")
        page.evaluate("""() => { window.__GRID['설정'][0][1] = '0629'; }""")

        # ---------- 잠금 ----------
        locks = page.evaluate("() => window.__locks")
        releases = page.evaluate("() => window.__releases")
        ok("쓰기마다 잠금 잡고 풀기", locks > 10 and locks == releases, {"locks": locks, "releases": releases})

        ok("알 수 없는 POST action", P({"action": "nope"})["body"].get("error") == "UNKNOWN_ACTION")

        browser.close()

    passed = sum(1 for x in results if x[0])
    print(f"\n=== {passed}/{len(results)} 통과 ===")
    for good, name, detail in results:
        if not good:
            print("  실패:", name, json.dumps(detail, ensure_ascii=False)[:400] if detail is not None else "")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
