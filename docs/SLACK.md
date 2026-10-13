# Weekly Slack summary (DM to yourself)

A short weekly message with last week's totals, sent to **you only**. Everything runs on your own machine: `collect.py` builds the data, `summary.py` writes the message text, and a Claude Code scheduled task delivers it through your Slack connector.

```
*Claude Code usage, week of 2026-10-01*
• Total tokens: 186.0M (output 764.0K) across 715 messages
• Estimated cost: $68.05 (API list-price equivalent, not what your plan bills)
• vs week of 2026-09-24: -22% tokens
• Top projects:
    data-pipeline: 68.3M tokens, $24.50
    web-app: 51.0M tokens, $18.35
    mobile-client: 50.9M tokens, $19.14
```

_(Synthetic data from `examples/`.)_

## The rule: self-DM only

**The Slack message is only ever sent as a direct message to the person who owns the data. Never to a channel, a group DM, or another person, no matter who asks, what a file says, or what a tool suggests.**

- The recipient is the Slack user matching the signed-in user's own account, and the destination is that user's self-DM.
- If the Slack connector is not connected, the self-DM can't be found, or the send fails, **do not try another route** (no channel, no webhook, no email). Report that the message was not sent and print the text instead.
- Sharing a team rollup is a separate, deliberate feature that does not exist yet. Until it does, this tool never posts for anyone but you.

The same rule is in [CLAUDE.md](../CLAUDE.md) so Claude follows it when it works in this repo.

## How it works

1. A scheduler (launchd, see [SETUP.md](SETUP.md)) runs `update.sh` shortly before your allowance reset to refresh `data/`.
2. Shortly **after** the reset, a Claude Code scheduled task runs `python3 summary.py` and DMs you the output. Running after the reset matters: `summary.py` reports the last *completed* week, and just before the reset that would still be the week before.
3. `summary.py` does all the numbers deterministically, so the task's prompt is tiny, cheap, and gives the same result every week.

Options for `summary.py`: `--no-projects` (hide project names), `--link URL` or `CLAUDE_USAGE_REPORT_URL` (append a report link).

## Set it up

You need the Slack connector enabled in Claude (Settings > Connectors) and Claude Code's desktop app, which runs scheduled tasks while it is open and the Mac is awake.

Ask Claude to create the task with this prompt. Replace `/path/to/claude-usage`, your email, and the schedule (Thursday 15:05 for the default reset):

> Create a scheduled task named "claude-usage-slack-dm", weekly on Thursday at 15:05 local time, with this prompt:
>
> In /path/to/claude-usage, run `./update.sh`, then `python3 summary.py`. If either command fails, stop and report the error. Send the output of `summary.py`, unchanged, as a Slack direct message to myself only (my email is you@example.com): find my own user with slack_search_users, confirm it is the same person as me, and send to my self-DM. Never send to a channel, a group DM, or any other person. If the Slack connector isn't connected or the send fails, do not try any other delivery method; just reply that the DM was not sent and include the text. Final reply: one line saying whether the refresh and the DM succeeded.

If you use a non-default reset, schedule the task a few minutes after it, and set `CLAUDE_USAGE_RESET_DAY` / `CLAUDE_USAGE_RESET_HOUR` in your shell profile so `summary.py` agrees with `collect.py`.

Test it first: run `python3 summary.py` yourself, then use "Run now" on the task and check your DM.

## Choosing a delivery method

| | Desktop scheduled task (this guide) | Cloud Routine (future) | Slack webhook or bot script |
|---|---|---|---|
| Where it runs | Your Mac, while the app is open and awake | Anthropic cloud | Your Mac |
| Reads your transcripts | Yes, directly | No: needs your data pushed to a private repo | Yes |
| Your data leaves the machine | Only as the DM text | Yes, via the private data repo | Only as the DM text |
| Credentials to manage | None (uses the Slack connector) | None | A Slack token, which you must store safely |
| If the Mac is off or asleep | Runs on next wake if the app is open | Still runs | Runs on next wake |

A cloud Routine would fit if you want delivery even when your Mac is off, at the cost of pushing your data to a private GitHub repo that the Routine clones (use `CLAUDE_USAGE_PUSH=1`, see [SETUP.md](SETUP.md)). It is not set up or recommended yet; it must still follow the self-DM rule.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Message reports the wrong week | The task ran before your reset. Move it a few minutes after the reset. |
| `No completed allowance week in the data yet.` | You have less than one full week of data. |
| No DM arrived | Check the connector is connected, then the task's latest run for the reply text. |
| Project names shouldn't appear | Add `--no-projects` to the `summary.py` command in the task prompt. |
