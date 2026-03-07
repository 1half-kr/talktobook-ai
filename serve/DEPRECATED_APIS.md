# 폐기된 API 목록

다음 API들은 새로운 명세에 따라 폐기되었습니다:

## 폐기된 엔드포인트들

1. **자서전 챕터 생성** - `POST /chapters/generate_chapters`
   - 이유: 챕터정보 생성 방식이 메타데이터가 아닌 덩어리 묶음방식을 따름

2. **자서전 교정/교열** - `POST /autobiographies/proofreading`  
   - 이유: 교정교열 기능이 필요 없음

3. **인터뷰 질문 생성** - `POST /interviews/interview-questions`
   - 이유: 메인 질문을 미리 생성하는 방식을 채택하지 않음

4. **인터뷰 대화 생성** - `POST /interviews/interview-chat`
   - 이유: 현재 사용하는 알고리즘이 아님

## 유지되는 엔드포인트들

1. **인터뷰 진행** - `POST /interviews/chat` (v2)
2. **대화 세션 시작** - `POST /interviews/start` (v2)  
3. **자서전 내용 생성** - `POST /autobiographies/generate` (수정됨)

## 폐기된 디렉토리들

- `chapters/generate_chapter/`
- `autobiographies/generate_correction/`
- `interviews/generate_interview_question/`
- `interviews/interview_chat/` (v1)