# Commit and push aiogram bridge changes to GitHub

Write-Host "=== Checking git status ===" -ForegroundColor Green
git status

Write-Host "`n=== Staging new files ===" -ForegroundColor Green
git add scripts/aiogram_bridge.py
git add requirements.txt
git add start_bridge.ps1
git add --intent-to-add logs/aiogram_bridge.log

Write-Host "`n=== Committing changes ===" -ForegroundColor Green
$message = @"
Stage L (Telegram Bridge): Implement aiogram async bridge with conversational layer

- Replace python-telegram-bot with aiogram 3.x (async, modern, performant)
- Add conversational prose generation with context retrieval
- Implement semantic search using nomic-embed-text
- Split routing: slash commands -> detailed handlers, natural questions -> conversational layer
- Add conversation history logging with response_type tagging
- Preserve all approval gates (R3/R4/R5/R8) and command routing
- Bot now responds naturally to questions like "How is marketing?" instead of generic help

Test results:
- "How is marketing?" -> Conversational prose about marketing status
- Multi-turn context awareness working
- "/board", "/status" still return detailed reports
- All R11 constraints maintained (local, no brokers, token in .env)

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>
"@

git commit -m $message

Write-Host "`n=== Pushing to GitHub ===" -ForegroundColor Green
git push origin HEAD

Write-Host "`n=== Verification ===" -ForegroundColor Cyan
git log --oneline -3
Write-Host "`n✅ Push complete!" -ForegroundColor Green
