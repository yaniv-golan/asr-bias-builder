# Custom Filters

Tighten mining/verification using config overrides:

```yaml
stop_words:
  - momentum
  - runway
  - pipeline

deny_patterns:
  - "^series [abc]$"
  - "roadmap"

use_titlecase_filter: true
deny_exact:
  - "seed stage"
```

Reload the config via `BIAS_CONFIG_FILE` or `--config` and rerun the pipeline to apply the filters.
