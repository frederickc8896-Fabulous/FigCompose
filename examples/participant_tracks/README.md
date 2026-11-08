# Aligned participant tracks / 环形多轨图

![Synthetic cohort](preview.png)

One angle is one participant. The three inner tracks show sex, ethnicity and response;
the two outer tracks show BMI and age. The open sector summarises those same people.
This is a ready-made `Figure.custom` template, rather than an additional built-in `kind`.

```bash
python -m pip install "FigCompose>=0.2.0"
python examples/participant_tracks/generate.py
python examples/participant_tracks/generate.py --data my_cohort.csv --out output/cohort
```

Download/clone the repository, then run the commands above; paths to input and style
are resolved beside the script, so the generator can also be called by absolute path.
Keep `examples/_export.py` when copying this example.

`data.csv` contains 72 simulated participants. Required columns:

| Column | Meaning / accepted values |
|---|---|
| `participant` | Nonempty unique ID |
| `age` | Years, 18–80; controls the common sample order |
| `bmi` | BMI, 15–42 |
| `sex` | Female / Male |
| `ethnicity` | Asian / Black / Caucasian / Hispanic |
| `response` | Sensitive / Intermediate / Resistant |

`style.yaml` uses the existing rose-blue swatches. Export is white-background PNG,
SVG and a smaller preview. Times New Roman is used when installed; otherwise a serif
fallback is reported. The template does not infer medical meaning or recode categories.

中文：每个角度对应同一个人，所有轨道按年龄排序；开口区是同一队列的总体摘要。
替换 CSV 即可使用现成模板，不需要重新编写环形排版。连续量尺和分类取值见上表。

[All examples](../README.md) · [FigCompose](../../README.md)
