# Dartness 관리 화면

사용자가 읽는 기준·실행·갱신·검사 한계는 [docs/management-screen.md](../docs/management-screen.md)를 따릅니다.

Node.js 24: `npm ci`, `npm run dev`. 검사: `npm run lint`, `npm test`, `npm run build`.

공개 상태 갱신: GitHub CLI 인증 후 `npm run snapshot`. 화면 다시 읽기는 GitHub를 재조회하지 않습니다. 토큰을 VITE 환경변수나 public/에 저장하지 않습니다.

Button은 MIT 라이선스의 shadcn/ui 구현을 바탕으로 이 프로젝트의 CSS에 맞게 수정했습니다. 나머지 화면은 프로젝트 구현입니다.
