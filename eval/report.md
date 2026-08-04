# Retrieval eval — keyword / semantic / hybrid

**10 queries × 3 engines × top-5**  — relevance judged automatically via keyword-group matching on result text.

## Per-query recall@5

| id  | difficulty  | query                                                 | keyword | semantic | hybrid |
|-----|-------------|-------------------------------------------------------|---------|----------|--------|
| e1  | easy        | card reader not working                               | 1.00   | 1.00   | 1.00   |
| e2  | easy        | IP camera installation                                | 1.00   | 1.00   | 1.00   |
| e3  | easy        | power supply failure                                  | 1.00   | 1.00   | 1.00   |
| p1  | paraphrase  | machine keeps shutting off by itself                  | 0.60   | 0.40   | 0.80   |
| p2  | paraphrase  | coin hopper eats notes and won't dispense             | 1.00   | 1.00   | 1.00   |
| p3  | paraphrase  | video feed is dark and grainy                         | 1.00   | 1.00   | 1.00   |
| p4  | paraphrase  | cabinet unresponsive to touch                         | 1.00   | 1.00   | 1.00   |
| h1  | hard        | table game equipment where results are hard to see fo | 0.20   | 0.00   | 0.00   |
| h2  | hard        | slot machine memory needs to be cleared               | 1.00   | 1.00   | 1.00   |
| h3  | hard        | network connectivity dropped at multiple locations    | 1.00   | 1.00   | 1.00   |

## Aggregate recall@5 by difficulty

| difficulty  | queries | keyword | semantic | hybrid |
|-------------|---------|---------|----------|--------|
| easy        |    3    | 1.00   | 1.00   | 1.00   |
| paraphrase  |    4    | 0.90   | 0.85   | 0.95   |
| hard        |    3    | 0.73   | 0.67   | 0.67   |

## Overall recall@5

| engine   | mean recall@5 |
|----------|---------------|
| keyword  | 0.88          |
| semantic | 0.84          |
| hybrid   | 0.88          |

## Mean latency (ms)

| engine   | mean ms |
|----------|---------|
| keyword  | 81     |
| semantic | 293     |
| hybrid   | 90     |
