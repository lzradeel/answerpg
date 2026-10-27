# Answer quality report

Run settings: 40 questions, k=5, `hybrid` retrieval, reranking on, answer backend `extractive` (extractive), faithfulness support threshold 0.8.

| metric | baseline | this run | change | status |
|---|---:|---:|---:|---|
| recall@5 | 0.963 | 0.963 | +0.000 | ok |
| mrr | 0.872 | 0.872 | +0.000 | ok |
| faithfulness | 1.000 | 1.000 | +0.000 | ok |
| answer_relevance | 0.798 | 0.798 | +0.000 | ok |
| answer_similarity | 0.778 | 0.778 | +0.000 | ok |

End-to-end time per question: p50 736.5 ms, p95 2242.4 ms. Average cost: $0.000000 per question.

## Retrieval modes side by side

| retriever | recall@5 | MRR | median ms |
|---|---:|---:|---:|
| keyword | 0.863 | 0.762 | 2.4 |
| semantic | 0.875 | 0.783 | 9.9 |
| hybrid | 0.875 | 0.760 | 12.1 |
| hybrid + rerank | 0.963 | 0.872 | 820.1 |

## Scores per question

| id | recall | 1/rank | faithfulness | relevance | similarity | ms |
|---|---:|---:|---:|---:|---:|---:|
| q01 | 1.00 | 1.00 | 1.00 | 0.832 | 0.731 | 674.1 |
| q02 | 1.00 | 1.00 | 1.00 | 0.727 | 0.939 | 506.9 |
| q03 | 1.00 | 1.00 | 1.00 | 0.915 | 0.839 | 540.8 |
| q04 | 1.00 | 1.00 | 1.00 | 0.914 | 0.926 | 1054.6 |
| q05 | 1.00 | 1.00 | 1.00 | 0.787 | 0.715 | 862.8 |
| q06 | 1.00 | 1.00 | 1.00 | 0.813 | 0.631 | 926.4 |
| q07 | 1.00 | 0.50 | 1.00 | 0.778 | 0.561 | 758.5 |
| q08 | 1.00 | 0.50 | 1.00 | 0.830 | 0.827 | 777.4 |
| q09 | 1.00 | 1.00 | 1.00 | 0.712 | 0.849 | 723.4 |
| q10 | 1.00 | 1.00 | 1.00 | 0.853 | 0.804 | 632.2 |
| q11 | 1.00 | 1.00 | 1.00 | 0.851 | 0.672 | 702.1 |
| q12 | 1.00 | 1.00 | 1.00 | 0.713 | 0.693 | 645.4 |
| q13 | 1.00 | 1.00 | 1.00 | 0.856 | 0.817 | 659.5 |
| q14 | 1.00 | 1.00 | 1.00 | 0.880 | 0.964 | 724.0 |
| q15 | 1.00 | 1.00 | 1.00 | 0.772 | 0.711 | 607.1 |
| q16 | 1.00 | 1.00 | 1.00 | 0.819 | 0.518 | 722.9 |
| q17 | 1.00 | 1.00 | 1.00 | 0.820 | 0.899 | 884.7 |
| q18 | 1.00 | 1.00 | 1.00 | 0.782 | 0.910 | 654.2 |
| q19 | 1.00 | 1.00 | 1.00 | 0.732 | 0.672 | 726.4 |
| q20 | 1.00 | 1.00 | 1.00 | 0.680 | 0.612 | 592.4 |
| q21 | 1.00 | 0.33 | 1.00 | 0.792 | 0.604 | 566.6 |
| q22 | 1.00 | 1.00 | 1.00 | 0.907 | 0.938 | 651.4 |
| q23 | 1.00 | 1.00 | 1.00 | 0.842 | 0.886 | 784.7 |
| q24 | 1.00 | 1.00 | 1.00 | 0.742 | 0.811 | 746.6 |
| q25 | 1.00 | 1.00 | 1.00 | 0.847 | 0.754 | 660.0 |
| q26 | 1.00 | 0.50 | 1.00 | 0.727 | 0.874 | 709.4 |
| q27 | 0.50 | 1.00 | 1.00 | 0.738 | 0.701 | 663.5 |
| q28 | 1.00 | 1.00 | 1.00 | 0.800 | 0.706 | 717.8 |
| q29 | 1.00 | 1.00 | 1.00 | 0.908 | 0.906 | 892.2 |
| q30 | 1.00 | 1.00 | 1.00 | 0.853 | 0.900 | 1162.9 |
| q31 | 0.00 | 0.00 | 1.00 | 0.612 | 0.667 | 1246.3 |
| q32 | 1.00 | 1.00 | 1.00 | 0.781 | 0.726 | 1415.8 |
| q33 | 1.00 | 0.20 | 1.00 | 0.735 | 0.727 | 2544.2 |
| q34 | 1.00 | 0.33 | 1.00 | 0.765 | 0.822 | 13315.8 |
| q35 | 1.00 | 1.00 | 1.00 | 0.854 | 0.931 | 2226.5 |
| q36 | 1.00 | 0.50 | 1.00 | 0.695 | 0.499 | 1379.5 |
| q37 | 1.00 | 1.00 | 1.00 | 0.895 | 0.802 | 1322.7 |
| q38 | 1.00 | 1.00 | 1.00 | 0.739 | 0.827 | 1202.2 |
| q39 | 1.00 | 1.00 | 1.00 | 0.921 | 0.975 | 1160.4 |
| q40 | 1.00 | 1.00 | 1.00 | 0.705 | 0.777 | 1637.3 |

## Questions below 1.0 on recall or faithfulness

- **q27** If SCIM deactivates someone, do we keep paying for their seat? (recall 0.50, faithfulness 1.00)  
  Reply: SCIM tokens do not expire [2]. Status: setting `active` to false deactivates the member [2].
- **q31** When my PR lands, does the matching ticket get marked finished on its own? (recall 0.00, faithfulness 1.00)  
  Reply: Match on the code in your integration, and log the `request_id`, which is also returned in the `X-Request-Id` header [1]. The `If-Match` revision you sent is older than the current one [1].
