import json
import shutil
import requests
import traceback
from pathlib import Path
from tkinter import Tk, filedialog

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Button, Label, Log
from textual.containers import Vertical, Horizontal
from textual.reactive import reactive


class StatusLog(Log):
  def append(self, message: str, style: str = "green") -> None:
    tag = {
      "green": "INFO",
      "yellow": "WARN",
      "red": "ERROR",
      "bold green": "SUCCESS",
      "bold red": "FATAL"
    }.get(style, "INFO")
    self.write(f"[{tag}] {message}")


class JsonFolderBuilder(App):
  CSS_PATH = None

  json_path = reactive("")
  save_path = reactive("")

  def compose(self) -> ComposeResult:
    yield Header()
    with Horizontal(id="main"):
      with Vertical(id="controls"):
        yield Label("📁 JSON 파일과 저장할 폴더를 선택하세요.")
        yield Button("🔍 JSON 파일 선택", id="select-json", variant="primary")
        yield Label("(선택 전)", id="json-label")
        yield Button("📂 저장 폴더 선택", id="select-dir", variant="primary")
        yield Label("(선택 전)", id="dir-label")
        yield Button("✅ 실행", id="run-btn", variant="success")
      yield StatusLog(id="log-box")
    yield Footer()

  def on_button_pressed(self, event: Button.Pressed) -> None:
    log = self.query_one(StatusLog)
    try:
      if event.button.id == "select-json":
        path = self.open_file_dialog()
        if path:
          self.json_path = path
          self.query_one("#json-label", Label).update(Path(path).name)
          log.append(f"JSON 파일 선택됨: {path}")

      elif event.button.id == "select-dir":
        path = self.open_folder_dialog()
        if path:
          self.save_path = path
          self.query_one("#dir-label", Label).update(Path(path).name)
          log.append(f"저장 폴더 선택됨: {path}")

      elif event.button.id == "run-btn":
        if not self.json_path:
          log.append("JSON 파일을 먼저 선택하세요.", style="red")
          return
        if not Path(self.json_path).is_file():
          log.append("올바른 JSON 파일을 선택하세요.", style="red")
          return
        if not self.save_path:
          log.append("저장 폴더를 먼저 선택하세요.", style="red")
          return
        json_text = Path(self.json_path).read_text(encoding="utf-8")
        self.process_json(json_text, self.save_path)
    except Exception:
      log.append(f"UI 처리 중 예외:\n{traceback.format_exc()}", style="bold red")

  def open_file_dialog(self) -> str:
    root = Tk(); root.withdraw()
    path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
    root.destroy(); return path

  def open_folder_dialog(self) -> str:
    root = Tk(); root.withdraw()
    path = filedialog.askdirectory()
    root.destroy(); return path

  def process_json(self, json_text: str, save_dir: str):
    log = self.query_one(StatusLog)
    try:
      data = json.loads(json_text)
      log.append("JSON 파싱 성공")
    except json.JSONDecodeError as e:
      log.append(f"JSONDecodeError: {e}. 후행 데이터 무시 시도", style="yellow")
      try:
        decoder = json.JSONDecoder()
        data, _ = decoder.raw_decode(json_text)
        log.append("후행 데이터 제거 후 파싱 성공", style="yellow")
      except Exception as e2:
        log.append(f"JSON 파싱 실패: {e2}", style="red")
        return
    except Exception as e:
      log.append(f"알 수 없는 파싱 에러: {e}", style="red")
      return

    try:
      name = data.get("name", "캐릭터").strip() or "캐릭터"
      base = Path(save_dir) / name
      base.mkdir(parents=True, exist_ok=True)

      def write_file(path: Path, content: str, label: str):
        path.write_text(content, encoding="utf-8")
        log.append(f"{label} 저장: {path.name}")

      write_file(base / "1_설명.txt", data.get("description", ""), "설명")
      prm = data.get("characterDetails") or data.get("customPrompt", "")
      write_file(base / "2_프롬프트.txt", prm, "프롬프트")

      init_msgs = data.get("initialMessages", [])
      default = data.get("defaultStartingSetSituationPrompt", "")
      global_replies = data.get("replySuggestions", [])
      if init_msgs:
        d1 = base / "대화상황1"
        d1.mkdir(exist_ok=True)
        write_file(d1 / "상황.txt", "\n\n".join(init_msgs), "대화상황1 메시지")
        write_file(d1 / "시작.txt", default, "대화상황1 시작")
        write_file(d1 / "예시.txt", "\n".join(global_replies), "대화상황1 예시")
      for idx, st in enumerate(data.get("startingSets", [])[:2], start=2):
        d = base / f"대화상황{idx}"
        d.mkdir(exist_ok=True)
        msgs = st.get("initialMessages", [])
        write_file(d / "상황.txt", "\n\n".join(msgs), f"대화상황{idx} 메시지")
        write_file(d / "시작.txt", st.get("situationPrompt", default), f"대화상황{idx} 시작")
        write_file(d / "예시.txt", "\n".join(st.get("replySuggestions", global_replies)), f"대화상況{idx} 예시")

      ce = data.get("chatExamples", [])
      if ce:
        ed = base / "대화예시"
        ed.mkdir(exist_ok=True)
        for i, ex in enumerate(ce, 1):
          lines = []
          if ex.get("user"): lines += ["[유저]", ex["user"]]
          if ex.get("character"): lines += ["[캐릭터]", ex["character"]]
          write_file(ed / f"예시_{i}.txt", "\n".join(lines), f"대화예시{i}")

      kb = data.get("keywordBook", [])
      if kb:
        kbd = base / "키워드북"
        kbd.mkdir(exist_ok=True)
        for grp in kb:
          nm = grp.get("name", "키워드북")
          kws = grp.get("keywords", [])
          pr = grp.get("prompt", "")
          safe = "".join(c if c not in r'\\/:*?"<>|' else "_" for c in nm)
          txt = [f"[키워드북명]{nm}"] + (["[목록]"] + [f"- {w}" for w in kws] if kws else []) + (["[설명]", pr] if pr else [])
          write_file(kbd / f"{safe}.txt", "\n".join(txt), f"키워드북:{nm}")

      imgs = data.get("situationImages", [])
      if imgs:
        imgd = base / "상황별 이미지"
        sub = imgd / "imgs"
        imgd.mkdir(exist_ok=True); sub.mkdir(exist_ok=True)
        info = []
        for idx, im in enumerate(imgs,1):
          url = im.get("imageUrl", ""); kw = im.get("keyword") or f"img{idx}"; sit = im.get("situation", "")
          ext = url.split('.')[-1].split('?')[0]
          p = sub / f"{kw}.{ext}"
          try:
            r = requests.get(url, timeout=10); r.raise_for_status(); p.write_bytes(r.content)
            log.append(f"이미지 다운로드: {kw}")
          except Exception as e:
            log.append(f"이미지 실패:{url}({e})", style="yellow")
          info.append(f"{kw}\t{sit}")
        write_file(imgd / "이미지_정보.txt", "\n".join(info), "이미지목록")

      prof = data.get("profileImage")
      url = prof.get("origin") if isinstance(prof, dict) else prof if isinstance(prof, str) else None
      if url:
        try:
          r = requests.get(url, timeout=10); r.raise_for_status()
          (base / "0_커버.png").write_bytes(r.content)
          log.append("프로필 이미지 저장")
        except Exception as e:
          log.append(f"프로필 이미지 실패:{e}", style="yellow")

      tags = data.get("tags", [])
      if tags:
        write_file(base / "3_태그.txt", "\n".join(tags), "태그")

      log.append(f"완료! 위치: {base}", style="bold green")
    except Exception:
      log.append(f"처리 예외:\n{traceback.format_exc()}", style="bold red")


if __name__ == "__main__":
  JsonFolderBuilder().run()
