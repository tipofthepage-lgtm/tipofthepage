// game.js — Tip of the Page client logic

function updateCard(data, feedbackMsg, feedbackType) {
  fetch('/render-state', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  })
  .then(r => r.text())
  .then(html => {
    document.getElementById('game-card').innerHTML = html;
    attachEvents();
    if (feedbackMsg) showFeedback(feedbackMsg, feedbackType);
    const input = document.getElementById('guess-input');
    if (input) input.focus();
  });
}

function showFeedback(msg, type) {
  const el = document.getElementById('feedback');
  if (el) {
    el.className = 'feedback ' + (type || 'info');
    el.textContent = msg;
  }
}

function handleGuess() {
  const input = document.getElementById('guess-input');
  const guess = (input?.value || '').trim();
  if (!guess) return;

  fetch('/guess', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ guess })
  })
  .then(r => r.json())
  .then(data => updateCard(data, data.feedback, data.feedback_type));
}

function nextQuote() {
  fetch('/next-quote', { method: 'POST' })
    .then(r => r.json())
    .then(data => {
      if (data.error) {
        alert(data.error);
        return;
      }
      updateCard(data);
    });
}

function playAgain() {
  if (typeof GAME_MODE === 'undefined') return;
  if (GAME_MODE === 'daily') {
    // Reload the daily page — server will serve same quote for today
    window.location.href = '/daily';
  } else {
    // Restart endless with same genre filter
    const genre = typeof GENRE_FILTER !== 'undefined' && GENRE_FILTER
      ? `?genre=${encodeURIComponent(GENRE_FILTER)}`
      : '';
    window.location.href = '/endless' + genre;
  }
}

function attachEvents() {
  const submitBtn   = document.getElementById('submit-btn');
  const input       = document.getElementById('guess-input');
  const nextBtn     = document.getElementById('next-quote-btn');
  const playAgainBtn= document.getElementById('play-again-btn');

  if (submitBtn)    submitBtn.addEventListener('click', handleGuess);
  if (input)        input.addEventListener('keydown', e => { if (e.key === 'Enter') handleGuess(); });
  if (nextBtn)      nextBtn.addEventListener('click', nextQuote);
  if (playAgainBtn) playAgainBtn.addEventListener('click', playAgain);
}

attachEvents();
