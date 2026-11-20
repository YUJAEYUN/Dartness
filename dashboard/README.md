# Dartness 관리 화면

사용자가 읽는 기준·실행·갱신·검사 한계는 [docs/management-screen.md](../docs/management-screen.md)를 따릅니다.

Node.js 24: `npm ci`, `npm run dev`. 검사: `npm run lint`, `npm test`, `npm run build`.

공개 상태 갱신: `npm run snapshot`. Vercel 빌드에서 자동 실행하며 실패하면 빌드도 실패합니다. 일반 CI·로컬 빌드는 저장된 파일을 사용합니다. 화면 다시 읽기는 GitHub를 재조회하지 않습니다. 토큰을 VITE 환경변수나 public/에 저장하지 않습니다.

Button은 MIT 라이선스의 shadcn/ui 구현을 바탕으로 이 프로젝트의 CSS에 맞게 수정했습니다. 나머지 화면은 프로젝트 구현입니다.

시스템 상태 원본은 ../docs/system-status.md입니다. 변경 후 `npm run docs:generate`로 생성 파일을 함께 커밋합니다. `npm run docs:check`는 필수 CI에서 실행합니다. `npm run hooks:install`로 로컬 pre-commit 검사를 설치할 수 있습니다. Vercel 빌드에는 저장소의 docs 디렉터리가 필요합니다.
