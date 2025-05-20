import json
from pathlib import Path
import requests

# JSON 로드
json_path = "FILEPATH"
with open(json_path, "r", encoding="utf-8") as f:
  data = json.load(f)

# 기본 폴더 생성 (캐릭터 이름 기반)
character_name = data.get("name", "캐릭터").strip()
base_dir = Path(f"FILEPATH{character_name}")
base_dir.mkdir(parents=True, exist_ok=True)

# 1. 설명 저장
desc = data.get("description", "")
(base_dir / "1. 설명.txt").write_text(desc, encoding="utf-8")

# 2. 프롬프트 저장 (characterDetails > customPrompt)
prompt_text = data.get("characterDetails") or data.get("customPrompt", "")
(base_dir / "2. 프롬프트.txt").write_text(prompt_text, encoding="utf-8")

# 3. 대화 템플릿/예시 저장
chat_examples = data.get("chatExamples", [])
starting_sets = data.get("startingSets", [])
initial_messages = data.get("initialMessages", [])

# 대화상황 폴더 저장 (최대 3개, 1번은 initialMessages 우선)
default_situation = data.get("defaultStartingSetSituationPrompt", "")
reply_suggestions_global = data.get("replySuggestions", [])

# 1번: initialMessages 기반
if initial_messages:
  conv1_dir = base_dir / "대화상황1"
  conv1_dir.mkdir(exist_ok=True)
  # 대화 상황 프롬프트
  (conv1_dir / "대화상황프롬프트.txt").write_text(
    "\n\n".join(initial_messages), encoding="utf-8"
  )
  # 시작 상황 프롬프트
  (conv1_dir / "시작상황프롬프트.txt").write_text(
    default_situation, encoding="utf-8"
  )
  # 예시 대화 프롬프트
  (conv1_dir / "예시대화프롬프트.txt").write_text(
    "\n".join(reply_suggestions_global), encoding="utf-8"
  )

# 2~3번: startingSets 기반
for idx, entry in enumerate(starting_sets[:2], start=2):
  conv_dir = base_dir / f"대화상황{idx}"
  conv_dir.mkdir(exist_ok=True)
  # 대화 상황 프롬프트
  messages = entry.get("initialMessages", [])
  (conv_dir / "대화상황프롬프트.txt").write_text(
    "\n\n".join(messages), encoding="utf-8"
  )
  # 시작 상황 프롬프트
  situation_prompt = entry.get("situationPrompt", default_situation)
  (conv_dir / "시작상황프롬프트.txt").write_text(
    situation_prompt, encoding="utf-8"
  )
  # 예시 대화 프롬프트
  reply_suggestions = entry.get("replySuggestions", reply_suggestions_global)
  (conv_dir / "예시대화프롬프트.txt").write_text(
    "\n".join(reply_suggestions), encoding="utf-8"
  )

# chatExamples 별도 저장
if chat_examples:
  chat_examples_dir = base_dir / "대화예시"
  chat_examples_dir.mkdir(exist_ok=True)
  for idx, example in enumerate(chat_examples, 1):
    user = example.get("user", "")
    character = example.get("character", "")
    lines = []
    if user:
      lines.append("[유저 프롬프트]")
      lines.append(user)
    if character:
      lines.append("\n[캐릭터 프롬프트]")
      lines.append(character)
    (chat_examples_dir / f"대화예시_{idx}.txt").write_text("\n".join(lines), encoding="utf-8")

# startingSets 템플릿 별도 저장
if starting_sets:
  for idx, entry in enumerate(starting_sets, 1):
    messages = entry.get("initialMessages", [])
    content = "\n".join(messages)
    
# 4. 키워드북 저장 (폴더 구조로)
keywords = data.get("keywordBook", [])
keywordbook_dir = base_dir / "키워드북"
keywordbook_dir.mkdir(exist_ok=True)
for group in keywords:
  group_name = group.get("name", "키워드북")
  group_keywords = group.get("keywords", [])
  group_prompt = group.get("prompt", "")
  lines = []
  lines.append(f"[키워드북명: ] {group_name}")
  if group_keywords:
    lines.append("[키워드 목록]")
    for kw in group_keywords:
      lines.append(f"- {kw}")
  if group_prompt:
    lines.append("\n[설명]")
    lines.append(group_prompt)
  # 파일명에 사용할 수 없는 문자는 _로 대체
  safe_name = "".join(c if c not in r'\/:*?"<>|' else "_" for c in group_name)
  (keywordbook_dir / f"{safe_name}.txt").write_text("\n".join(lines), encoding="utf-8")

# 5. 이미지 URL 목록 저장 및 상황별 이미지 다운로드 (keyword를 파일명으로)
situation_images = data.get("situationImages", [])
image_dir = base_dir / "상황별 이미지"
imgs_dir = image_dir / "imgs"
image_dir.mkdir(exist_ok=True)
imgs_dir.mkdir(exist_ok=True)
image_info_lines = []
for img in situation_images:
  url = img.get("imageUrl")
  keyword = img.get("keyword", "")
  situation = img.get("situation", "")
  if url:
    # 파일명: keyword가 있으면 keyword, 없으면 image_{idx}
    if keyword:
      ext = url.split('.')[-1].split('?')[0]
      img_path = imgs_dir / f"{keyword}.{ext}"
    else:
      ext = url.split('.')[-1].split('?')[0]
      idx = len(image_info_lines) + 1
      img_path = imgs_dir / f"image_{idx}.{ext}"
    try:
      response = requests.get(url, timeout=10)
      response.raise_for_status()
      with open(img_path, "wb") as f:
        f.write(response.content)
    except Exception as e:
      print(f"이미지 다운로드 실패: {url} ({e})")
    # keyword와 situation 쌍으로 저장
    image_info_lines.append(f"{keyword}\t{situation}")

# 이미지 정보 txt를 상황별 이미지 폴더에 저장
(image_dir / "이미지_정보목록.txt").write_text("\n".join(image_info_lines), encoding="utf-8")

# 프로필 이미지(origin) png로 저장
profile_image_url = ""
if "profileImage" in data:
  if isinstance(data["profileImage"], dict):
    profile_image_url = data["profileImage"].get("origin", "")
  elif isinstance(data["profileImage"], str):
    profile_image_url = data["profileImage"]
if profile_image_url:
  try:
    response = requests.get(profile_image_url, timeout=10)
    response.raise_for_status()
    with open(base_dir / "0. 커버_이미지.png", "wb") as f:
      f.write(response.content)
  except Exception as e:
    print(f"커버 이미지 다운로드 실패: {profile_image_url} ({e})")

# 태그 저장
tags = data.get("tags", [])
if tags:
  (base_dir / "3. 태그.txt").write_text("\n".join(tags), encoding="utf-8")

print(f"✅ 폴더 생성 및 파일 저장 완료: {base_dir}")