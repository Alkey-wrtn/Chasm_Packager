import json
import shutil
import requests
import traceback
import sys

from pathlib import Path
from PIL import Image
from pathlib import Path
from tkinter import Tk, filedialog

from rich.text import Text
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Button, Label, Log
from textual.containers import Vertical, Horizontal
from textual.reactive import reactive
from textual_imageview.viewer import ImageViewer


def resource_path(relative_path: str) -> Path:
  if hasattr(sys, "_MEIPASS"):
    return Path(sys._MEIPASS) / relative_path  # type: ignore
  return Path(relative_path)


class ChasmPackager(App):
  CSS_PATH = resource_path("styles.tcss")

  json_path = reactive("")
  save_path = reactive("")

  def compose(self) -> ComposeResult:
    yield Header()
    with Horizontal(id="main"):
      with Vertical(id="controls"):
        yield Label("📁 JSON 파일과 저장할 폴더를 선택해주세요.")
        yield Label(" ")
        yield Button("🔍 JSON 파일 선택", id="select-json", variant="primary")
        yield Label("(JSON 파일이 선택되지 않았습니다.)", id="json-label")
        yield Label(" ")
        yield Button("📂 저장될 폴더 선택", id="select-dir", variant="primary")
        yield Label("(저장될 폴더가 선택되지 않았습니다.)", id="dir-label")
        yield Label(" ")
        yield Button("✅ 실행", id="run-btn", variant="success")
        yield Label(" ")
        yield Label(" ")
        yield Label(
          "🔶 ChasmCopyPackager v2.0.0 - By Alkey\n"
          "🔶 오류나 추가 기능 문의가 있다면 Discord: crk_alkey로 문의 부탁드려요!",
          id="green"
        )
        yield Label(" ")
        yield Label("🔷 (Ctrl + Q)를 누르면 프로그램을 종료해요.", id="yellow")
        yield ImageViewer(Image.open(resource_path("chibialkey.png")))
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
          log.write(f"🟢 JSON 파일 선택됨: {path}\n")

      elif event.button.id == "select-dir":
        path = self.open_folder_dialog()
        if path:
          self.save_path = path
          self.query_one("#dir-label", Label).update(Path(path).name)
          log.write(f"🟢 저장 폴더 선택됨: {path}\n")

      elif event.button.id == "run-btn":
        if not self.json_path:
          log.write("🔴 JSON 파일을 먼저 선택하세요.\n")
          return
        if not Path(self.json_path).is_file():
          log.write("🔴 올바른 JSON 파일을 선택하세요.\n")
          return
        if not self.save_path:
          log.write("🔴 저장 폴더를 먼저 선택하세요.\n")
          return
        json_text = Path(self.json_path).read_text(encoding="utf-8")
        self.process_json(json_text, self.save_path)
    except Exception:
      log.write(f"❌ UI 처리 중 예외:\n{traceback.format_exc()}\n")

  def open_file_dialog(self) -> str:
    root = Tk()
    root.withdraw()
    path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
    root.destroy()
    return path

  def open_folder_dialog(self) -> str:
    root = Tk()
    root.withdraw()
    path = filedialog.askdirectory()
    root.destroy()
    return path

  def process_json(self, json_text: str, save_dir: str):
    log = self.query_one(Log)

    def l(msg: str, style: str = None):  # type: ignore
      tag = f"[{style}]" if style else ""
      end = f"[/{style}]" if style else ""
      log.write(f"{tag}{msg}{end}\n")

    try:
      data = json.loads(json_text)
      l("🟢 JSON 파싱 성공")
    except json.JSONDecodeError as e:
      l(f"🟡 파싱 오류: {e}. 후행 데이터 무시 시도")
      try:
        data, _ = json.JSONDecoder().raw_decode(json_text)
        l("🟡 후행 데이터 제거 후 파싱 성공")
      except Exception as e2:
        l(f"🔴 JSON 파싱 실패: {e2}")
        return
    except Exception as e:
      l(f"🔴 알 수 없는 파싱 에러: {e}")
      return

    try:
      name = data.get("name", "캐릭터").strip() or "캐릭터"
      base_dir = Path(save_dir) / name
      base_dir.mkdir(parents=True, exist_ok=True)

      def write(path: Path, content: str, label: str):
        path.write_text(content, encoding="utf-8")
        l(f"✅ {label} 저장: {path.name}")

      def safe_name(text: str) -> str:
        return "".join(c if c not in r'\\/:*?"<>|' else "_" for c in text)

      def save_keyword_book_helper(kb_data, target_dir):
        if not kb_data:
          return
        kb_dir = target_dir / "키워드북"
        kb_dir.mkdir(exist_ok=True)
        for grp in kb_data:
          nm = grp.get("name", "키워드북")
          safe = safe_name(nm)
          kws = grp.get("keywords", [])
          pr = grp.get("prompt", "")
          lines = [f"[키워드북명]\n{nm}"]
          if kws:
            lines += ["", "[키워드 목록]"] + [f"- {w}" for w in kws]
          if pr:
            lines += ["", "[설명]", pr]
          write(kb_dir / f"{safe}.txt", "\n".join(lines), f"키워드북 '{nm}'")

      def save_situation_images_helper(si_data, target_dir):
        if not si_data:
          return
        img_dir = target_dir / "상황별 이미지"
        imgs = img_dir / "imgs"
        img_dir.mkdir(exist_ok=True)
        imgs.mkdir(exist_ok=True)
        info = []
        for i, img in enumerate(si_data, 1):
          url = img.get("imageUrl") or img.get("blurredImageUrl")
          kw = img.get("keyword", f"image_{i}")
          sit = img.get("situation", "")
          if not url:
            continue
          ext = url.split(".")[-1].split("?")[0]
          p = imgs / f"{kw}.{ext}"
          try:
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            p.write_bytes(r.content)
            l(f"🖼️  이미지 다운로드 완료: {kw}")
          except Exception as e:
            l(f"⚠️  이미지 다운로드 실패: {url} ({e})", "yellow")
          info.append(f"{kw}\t{sit}")
        write(img_dir / "이미지_정보목록.txt", "\n".join(info), "이미지 정보 목록")

      # 1. 설명 저장 (확장)
      desc_parts = []
      if data.get("description"):
        desc_parts.append("[Description]\n" + data["description"])
      if data.get("simpleDescription"):
        desc_parts.append("\n[Simple Description]\n" + data["simpleDescription"])
      if data.get("detailDescription"):
        desc_parts.append("\n[Detail Description]\n" + data["detailDescription"])
      write(base_dir / "1. 설명.txt", "\n".join(desc_parts), "설명")

      # 플레이 가이드
      if data.get("playGuide"):
        lore_dir = base_dir / "세계관"
        lore_dir.mkdir(exist_ok=True)
        write(lore_dir / "플레이_가이드.txt", data["playGuide"], "플레이 가이드")

      # 2. 프롬프트 저장 (기존 유지)
      character_details = data.get("characterDetails")
      custom_prompt = data.get("customPrompt", "")
      if character_details and custom_prompt:
        write(base_dir / "2. 기본 프롬프트.txt", character_details, "기본 프롬프트")
        write(base_dir / "2. 커스텀 프롬프트.txt", custom_prompt, "커스텀 프롬프트")
      else:
        prompt = character_details or custom_prompt or ""
        write(base_dir / "2. 프롬프트.txt", prompt, "프롬프트")

      # 7. profileImage
      prof = data.get("profileImage")
      url = prof.get("origin") if isinstance(prof, dict) else prof if isinstance(prof, str) else None
      if url:
        try:
          r = requests.get(url, timeout=10)
          r.raise_for_status()
          (base_dir / "0. 커버_이미지.webp").write_bytes(r.content)
          l("🖼️  프로필 이미지 저장 완료")
        except Exception as e:
          l(f"⚠️  프로필 이미지 실패: {e}", "yellow")

      # 8. tags
      if data.get("tags"):
        write(base_dir / "3. 태그.txt", "\n".join(data["tags"]), "태그")

      # 스탯 저장
      if data.get("stats"):
        stats_dir = base_dir / "스탯"
        stats_dir.mkdir(exist_ok=True)
        write(
          stats_dir / "stats.json",
          json.dumps(data["stats"], ensure_ascii=False, indent=2),
          "스탯 JSON"
        )
        lines = ["[스탯 목록]\n"]
        for s in data["stats"]:
          lines.append(
            f"- {s.get('name')}\n"
            f"  초기값: {s.get('initial')}\n"
            f"  범위: {s.get('min')} ~ {s.get('max')}\n"
          )
        write(stats_dir / "stats_readme.txt", "\n".join(lines), "스탯 설명")

      # 엔딩 저장
      if data.get("endings"):
        end_dir = base_dir / "엔딩"
        end_dir.mkdir(exist_ok=True)
        write(
          end_dir / "endings.json",
          json.dumps(data["endings"], ensure_ascii=False, indent=2),
          "엔딩 JSON"
        )
        for i, e in enumerate(data["endings"], 1):
          title = safe_name(e.get("title", f"엔딩{i}"))
          body = []
          if e.get("conditions"):
            body.append("[조건]")
            body.append(json.dumps(e["conditions"], ensure_ascii=False, indent=2))
          if e.get("text"):
            body.append("\n[엔딩 텍스트]\n" + e["text"])
          write(end_dir / f"{i:02d}_{title}.txt", "\n".join(body), "엔딩 텍스트")

      # JSON 포맷 감지
      is_new_format = "defaultStartingSetSituationPrompt" not in data and "startingSets" in data

      if is_new_format:
        l("🟢 새로운 JSON 포맷 감지. 각 대화상황별로 리소스를 저장합니다.")
        dialogues_dir = base_dir / "대화상황"
        dialogues_dir.mkdir(exist_ok=True)

        for idx, st in enumerate(data.get("startingSets", []), start=1):
          folder_name = safe_name(st.get("name", f"대화상황{idx}"))
          d = dialogues_dir / f"{idx}_{folder_name}"
          d.mkdir(exist_ok=True)

          msgs = st.get("initialMessages", [])
          write(d / "대화상황프롬프트.txt", "\n\n".join(msgs), f"대화상황{idx} 메시지")
          write(d / "시작상황프롬프트.txt", st.get("situationPrompt", ""), f"대화상황{idx} 시작")
          write(d / "예시대화프롬프트.txt", "\n".join(st.get("replySuggestions", [])), f"대화상황{idx} 예시")

          if st.get("playGuide"):
            write(d / "플레이_가이드.txt", st["playGuide"], "상황별 플레이 가이드")

      if is_new_format:
        dialogues_dir = base_dir / "대화상황"
        dialogues_dir.mkdir(exist_ok=True)

        for idx, st in enumerate(data.get("startingSets", []), start=1):
          folder_name = safe_name(st.get("name", f"대화상황{idx}"))
          d = dialogues_dir / f"{idx}_{folder_name}"
          d.mkdir(exist_ok=True)

          if st.get("parameters"):
            lines = []
            for p in st["parameters"]:
              lines.extend([
                f"[스탯] {p.get('name','')}",
                f"설명: {p.get('prompt','')}",
                f"범위: {p.get('min')} ~ {p.get('max')}",
                f"초기값: {p.get('initialValue')}",
                f"단위: {p.get('unit','')}",
                ""
              ])
            write(d / "스탯.txt", "\n".join(lines).strip(), "스탯")

          if st.get("ending"):
            e = st["ending"]
            lines = [f"[턴 제한]\n{e.get('turns')}"]
            for ed in e.get("endings", []):
              lines.extend([
                "",
                "[엔딩 이름]",
                ed.get("name",""),
                "",
                "[조건 설명]",
                ed.get("conditionPrompt",""),
                "",
                "[엔딩 조건 파라미터]"
              ])
              for pc in ed.get("parameterConditions", []):
                lines.append(
                  f"- {pc.get('parameterName')} {pc.get('operator')} {pc.get('value')}"
                )
              lines.extend([
                "",
                "[에필로그 예시]",
                ed.get("epilogueExample",""),
                "",
                "[힌트]",
                ed.get("hint","")
              ])
            write(d / "엔딩.txt", "\n".join(lines).strip(), "엔딩")
          if st.get("keywordBook"):
            save_keyword_book_helper(st.get("keywordBook"), d)
          if st.get("situationImages"):
            save_situation_images_helper(st.get("situationImages"), d)
            
      else:
        l("🟡 기존 JSON 포맷 감지. 리소스를 최상위 폴더에 저장합니다.")
        init = data.get("initialMessages", [])
        default = data.get("defaultStartingSetSituationPrompt", "")
        replies = data.get("replySuggestions", [])
        dialogues_dir = base_dir / "대화상황"
        dialogues_dir.mkdir(exist_ok=True)

        if init:
          d1 = dialogues_dir / "대화상황1"
          d1.mkdir(exist_ok=True)
          write(d1 / "대화상황프롬프트.txt", "\n\n".join(init), "대화상황1 메시지")
          write(d1 / "시작상황프롬프트.txt", default, "대화상황1 시작")
          write(d1 / "예시대화프롬프트.txt", "\n".join(replies), "대화상황1 예시")

        for idx, st in enumerate(data.get("startingSets", [])[:2], start=2):
          d = dialogues_dir / f"대화상황{idx}"
          d.mkdir(exist_ok=True)
          msgs = st.get("initialMessages", [])
          write(d / "대화상황프롬프트.txt", "\n\n".join(msgs), f"대화상황{idx} 메시지")
          write(d / "시작상황프롬프트.txt", st.get("situationPrompt", default), f"대화상황{idx} 시작")
          write(d / "예시대화프롬프트.txt", "\n".join(st.get("replySuggestions", replies)), f"대화상황{idx} 예시")

        if data.get("keywordBook"):
          save_keyword_book_helper(data.get("keywordBook"), base_dir)
        if data.get("situationImages"):
          save_situation_images_helper(data.get("situationImages"), base_dir)

      # 대화 예시
      if data.get("chatExamples"):
        ex_dir = base_dir / "대화예시"
        ex_dir.mkdir(exist_ok=True)
        for i, ex in enumerate(data["chatExamples"], 1):
          lines = []
          if ex.get("user"):
            lines += ["[유저 프롬프트]", ex["user"]]
          if ex.get("character"):
            lines += ["", "[캐릭터 프롬프트]", ex["character"]]
          write(ex_dir / f"대화예시_{i}.txt", "\n".join(lines), f"대화예시{i}")

      l(f"🎉 완료! 폴더 생성 위치: {base_dir}")
    except Exception:
      l(f"❌ [오류] 처리 중 예외 발생:\n{traceback.format_exc()}")

if __name__ == "__main__":
  ChasmPackager().run()