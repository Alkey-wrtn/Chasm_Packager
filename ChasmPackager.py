import json
import shutil
import requests
import traceback
from pathlib import Path
from tkinter import Tk, filedialog

from rich.text import Text
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Button, Label, Log
from textual.containers import Vertical, Horizontal
from textual.reactive import reactive

class ChasmPackager(App):
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
      yield Log(id="log-box")
    yield Footer()

  def on_button_pressed(self, event: Button.Pressed) -> None:
    log = self.query_one(Log)
    try:
      if event.button.id == "select-json":
        path = self.open_file_dialog()
        if path:
          self.json_path = path
          self.query_one("#json-label", Label).update(Path(path).name)
          log.write(f"[green]JSON 파일 선택됨: {path}[/green]\n")

      elif event.button.id == "select-dir":
        path = self.open_folder_dialog()
        if path:
          self.save_path = path
          self.query_one("#dir-label", Label).update(Path(path).name)
          log.write(f"[green]저장 폴더 선택됨: {path}[/green]\n")

      elif event.button.id == "run-btn":
        if not self.json_path:
          log.write("[red]JSON 파일을 먼저 선택하세요.[/red]\n")
          return
        if not Path(self.json_path).is_file():
          log.write("[red]올바른 JSON 파일을 선택하세요.[/red]\n")
          return
        if not self.save_path:
          log.write("[red]저장 폴더를 먼저 선택하세요.[/red]\n")
          return
        json_text = Path(self.json_path).read_text(encoding="utf-8")
        self.process_json(json_text, self.save_path)
    except Exception:
      log.write(f"[bold red]UI 처리 중 예외:\n{traceback.format_exc()}[/bold red]\n")

  def open_file_dialog(self) -> str:
    root = Tk(); root.withdraw()
    path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
    root.destroy(); return path

  def open_folder_dialog(self) -> str:
    root = Tk(); root.withdraw()
    path = filedialog.askdirectory()
    root.destroy(); return path

  def process_json(self, json_text: str, save_dir: str):
    log = self.query_one(Log)
    def l(msg: str, style: str = None):
      tag = f"[{style}]" if style else ""
      end = f"[/{style}]" if style else ""
      log.write(f"{tag}{msg}{end}\n")

    try:
      data = json.loads(json_text)
      l("JSON 파싱 성공", "green")
    except json.JSONDecodeError as e:
      l(f"파싱 오류: {e}. 후행 데이터 무시 시도", "yellow")
      try:
        data, _ = json.JSONDecoder().raw_decode(json_text)
        l("후행 데이터 제거 후 파싱 성공", "yellow")
      except Exception as e2:
        l(f"JSON 파싱 실패: {e2}", "red")
        return
    except Exception as e:
      l(f"알 수 없는 파싱 에러: {e}", "red")
      return

    try:
      name = data.get("name", "캐릭터").strip() or "캐릭터"
      base_dir = Path(save_dir) / name
      base_dir.mkdir(parents=True, exist_ok=True)

      def write(path: Path, content: str, label: str):
        path.write_text(content, encoding="utf-8")
        l(f"{label} 저장: {path.name}")

      # 1. 설명 저장
      write(base_dir / "1. 설명.txt", data.get("description", ""), "설명")
      
      # 2. 프롬프트 저장
      prompt = data.get("characterDetails") or data.get("customPrompt", "")
      write(base_dir / "2. 프롬프트.txt", prompt, "프롬프트")

      # 3. 대화상황 저장
      init = data.get("initialMessages", [])
      default = data.get("defaultStartingSetSituationPrompt", "")
      replies = data.get("replySuggestions", [])
      if init:
        d1 = base_dir / "대화상황1"; d1.mkdir(exist_ok=True)
        write(d1 / "대화상황프롬프트.txt", "\n\n".join(init), "대화상황1 메시지")
        write(d1 / "시작상황프롬프트.txt", default, "대화상황1 시작")
        write(d1 / "예시대화프롬프트.txt", "\n".join(replies), "대화상황1 예시")

      for idx, st in enumerate(data.get("startingSets", [])[:2], start=2):
        d = base_dir / f"대화상황{idx}"; d.mkdir(exist_ok=True)
        msgs = st.get("initialMessages", [])
        write(d / "대화상황프롬프트.txt", "\n\n".join(msgs), f"대화상황{idx} 메시지")
        write(d / "시작상황프롬프트.txt", st.get("situationPrompt", default), f"대화상황{idx} 시작")
        write(d / "예시대화프롬프트.txt", "\n".join(st.get("replySuggestions", replies)), f"대화상황{idx} 예시")

      # 4. chatExamples (대화 예시 저장)
      if data.get("chatExamples"):
        ex_dir = base_dir / "대화예시"; ex_dir.mkdir(exist_ok=True)
        for i, ex in enumerate(data["chatExamples"], 1):
          lines = []
          if ex.get("user"): lines += ["[유저 프롬프트]", ex["user"]]
          if ex.get("character"): lines += ["", "[캐릭터 프롬프트]", ex["character"]]
          write(ex_dir / f"대화예시_{i}.txt", "\n".join(lines), f"대화예시{i}")

      # 5. keywordBook (키워드북 내용 및 키워드 저장)
      if data.get("keywordBook"):
        kb_dir = base_dir / "키워드북"; kb_dir.mkdir(exist_ok=True)
        for grp in data["keywordBook"]:
          nm = grp.get("name", "키워드북")
          safe = "".join(c if c not in r'\\/:*?"<>|' else "_" for c in nm)
          kws = grp.get("keywords", [])
          pr = grp.get("prompt", "")
          lines = [f"[키워드북명: ] {nm}"]
          if kws: lines += ["[키워드 목록]"] + [f"- {w}" for w in kws]
          if pr: lines += ["", "[설명]", pr]
          write(kb_dir / f"{safe}.txt", "\n".join(lines), f"키워드북 '{nm}'")

      # 6. situationImages (상황별 이미지 저장)
      if data.get("situationImages"):
        img_dir = base_dir / "상황별 이미지"
        imgs = img_dir / "imgs"
        img_dir.mkdir(exist_ok=True); imgs.mkdir(exist_ok=True)
        info = []
        for i, img in enumerate(data["situationImages"], 1):
          url = img.get("imageUrl", "")
          kw = img.get("keyword", f"image_{i}")
          sit = img.get("situation", "")
          ext = url.split('.')[-1].split('?')[0]
          p = imgs / f"{kw}.{ext}"
          try:
            r = requests.get(url, timeout=10); r.raise_for_status(); p.write_bytes(r.content)
            l(f"🖼️ 이미지 다운로드 완료: {kw}")
          except Exception as e:
            l(f"⚠️ 이미지 다운로드 실패: {url} ({e})", "yellow")
          info.append(f"{kw}\t{sit}")
        write(img_dir / "이미지_정보목록.txt", "\n".join(info), "이미지 정보 목록")

      # 7. profileImage (커버 이미지 저장)
      prof = data.get("profileImage")
      url = prof.get("origin") if isinstance(prof, dict) else prof if isinstance(prof, str) else None
      if url:
        try:
          r = requests.get(url, timeout=10); r.raise_for_status(); (base_dir / "0. 커버_이미지.png").write_bytes(r.content)
          l("🖼️ 프로필 이미지 저장 완료")
        except Exception as e:
          l(f"⚠️ 프로필 이미지 실패: {e}", "yellow")

      # 8. tags (태그 저장)
      if data.get("tags"):
        write(base_dir / "3. 태그.txt", "\n".join(data["tags"]), "태그")

      l(f"🎉 완료! 폴더 생성 위치: {base_dir}", "bold green")
    except Exception:
      l(f"[오류] 처리 중 예외 발생:\n{traceback.format_exc()}", "bold red")

if __name__ == "__main__":
  ChasmPackager().run()
