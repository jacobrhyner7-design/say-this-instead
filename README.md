# Say This Instead autopilot

Posts work and money "what to say" scripts to @saythis.instead on TikTok, Instagram and Facebook at 7:30am, 12:15pm and 8pm Central.

- `data/queue.json`: the hand-written first posts, each with its own pictures in `engine/scenes/posts/`.
- `engine/generate.py`: writes new posts with the Claude API when the queue runs out (sales posts follow NEPQ).
- `config.json`: times, warm-up ramp, account IDs, launch date. Nothing posts before `launch_date`.
- `python engine/assign_slots.py YYYY-MM-DD` sets the launch date and gives every queued post a slot.
- Push `data/check.json` to refresh post statuses (`data/status-check.json`) and the Blotato account list (`data/facebook-accounts.json`).

Secrets: BLOTATO_API_KEY, ELEVENLABS_API_KEY, ANTHROPIC_API_KEY.
