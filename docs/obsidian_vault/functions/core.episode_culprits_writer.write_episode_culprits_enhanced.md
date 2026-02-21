---
type: function
id: core.episode_culprits_writer.write_episode_culprits_enhanced
module: core.episode_culprits_writer
source: core/episode_culprits_writer.py
line_start: 262
line_end: 341
generated_at: 2026-02-21T06:33:21+00:00
tags:
  - acm
  - function
---

# core.episode_culprits_writer.write_episode_culprits_enhanced

Defined in: [[modules/core.episode_culprits_writer|core.episode_culprits_writer]]

Source: `core/episode_culprits_writer.py:262`

Kind: `function`

Signature: `write_episode_culprits_enhanced(sql_client, run_id: str, episodes: pd.DataFrame, scores_df: pd.DataFrame, equip_id: Optional[int]=None)`

Summary: Enhanced version that computes detector contributions from scores.
