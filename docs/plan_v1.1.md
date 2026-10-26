# 新研究 v1.1 計画書 — 現行研究 v1.0 の再実施（群定義バグ修正版）

- 作成日: 2026-10-07、改訂 2026-10-08（具体化・語弊修正）
- 改訂内容: データ量・期間・SESOI・neg_gapの単位/条件明示、RFフル格子と校正6点の区別、Gのgate不使用の明示、パイロット/本番・n/CIの明示、core/topメンバ固定、100-sham工数の段階実行化、P_only禁止テストの厳密化
- パス表記: 本書の `現行研究 v1.0/...` は `<PC>/研究/広大シンポジウム/現行研究 v1.0/...` を指す。`新研究 v1.1/...` は `<PC>/研究/広大シンポジウム/新研究 v1.1/...` を指す。
- 親研究: `現行研究 v1.0` / `perdigao_attribution`（状態 `CALIBRATION_FAILED`、P5確定）
- 位置づけ: 同一手順の再実施（re-run）＋ 内部凍結による修正再実行。**OSF登録は行わない**（前提）。現行の tag / hash を流用しない。新規に内部凍結（git tag＋freeze_manifest＋freeze_bundleローカル保管）のみ行う。
- OSFなしの格下げ: 本研究は事前登録を欠くため、確証的強度は現行（XETYJ登録済み）より一段低い「内部凍結準確証・探索的確証」に留まる。一次判定が出ても「事前登録済み」とは表現しない。HARKing・p-hacking対策として凍結後の変更禁止・exposure log・全試行開示を維持する（§5参照）。
- 確認密封継承: 現行は `runs/exposure.jsonl` なし＝確認未開封（`現行研究 v1.0/perdigao_attribution/STATUS.md:18`）。本計画はこの密封を前提に再利用する。開封済みなら本計画は破棄し別設計にする。
- 作業ルート: `<PC>/研究/広大シンポジウム/新研究 v1.1/`
- 実装先（新規・分離）: `新研究 v1.1/perdigao_attribution_v1.1/`（現行 `現行研究 v1.0/perdigao_attribution/` は読出し専用・変更禁止）

## 0. 結論（1本化）

> **物理変換特徴は有限標本の風速予報に物理固有の帰納バイアスを与えるか — Perdigão 公開タワー観測を用いた再現・反証研究 v1.1（群定義修正・再校正）**

現行 `現行研究 v1.0/PLAN.md:5-10` と同一の問い・データ・判定5条件を維持し、主犯バグ（P群定義欠落）の修正を核としつつ、補足研究αで特定された副因（列数・DGP単一・sham proxy）への事前固定の拡張を含めて P0→P5 をもう一度行う。結果が正でも負でも報告する。追加データ源（HRRR/GFS/衛星/WeatherBench2等）は混ぜない。

## 1. 現行研究の調査要約

### 1.1 問い・範囲（変更なし）

- 問い: 同一観測 `X` からの物理変換 `P=f(X)` は新情報ゼロでも初見予測を良くするか。推定は帰納バイアスのみ、因果証明なし（`現行研究 v1.0/PLAN.md:49-53`）。「新情報ゼロ」とは `P` が全親変数 `X` から決定論的に作られ、`X` を与えた条件では情報を追加しないという意味である。
- 対象: Perdigão 北稜線 tse13（地上標高452.9m）、100m streamwise風速、1時間先（一次）。データは NSF NCAR/EOL dataset 536.011 v1.2、DOI `10.26023/ZDMJ-D1TY-FG14` のみ。公称503MB、実測 NetCDF 175ファイル合計527015036 bytes（`tables/p5_report_values.csv:total_bytes, n_nc_files`、`reports/final_report.md:71-72`）。
- 期間: 開発 2016-11-29T00:00Z以上〜2017-03-10T00:00Z未満、確認 2017-03-10T00:00Z以上〜2017-06-17T00:00Z未満（6/16終日含む。確認は14日連続ブロック×8 outer folds、purge 3h）。2017-06-17以降は将来の独立確認候補として未読維持（`MuseSpark1.3_実装手順書/01_実装構成と共通契約.md:67-71`、`OSF登録_完全版_20260916.md:174`）。

### 1.2 手順（現行 P0–P5）

| Phase | 内容 | 現行手順書 | 現行結果 |
|---|---|---|---|
| P0 | 環境・契約試験 | `02_フェーズP0-P1_環境・取得・凍結.md:3-34` | P0_COMPLETE |
| P1 | 取得・監査・凍結 | 同上後半 | P1_FROZEN、tag `preregistered-design-20260915`、manifest `794b1347…`、SESOI 0.008862 m/s（開発BCA RMSE 0.886165 m/sの1%）、確認common-mask率85.26%（24310/28512、基準70%でPASS） |
| U | OSF事前登録 | `08_ユーザーが行うこと.md:27-63` | https://osf.io/xetyj (XETYJ、2026-09-20 08:47 UTC public) |
| P2 | R0 paper-spec / R1 code-spec / R2 corrected 各1回 | `03_フェーズP2_原研究再現.md:16-39` | persistenceのみ一致、BCA/ARIMA-RF不一致（12行監査、UNSPECIFIED含む） |
| P3 | 半合成校正1200反復→合格時のみCONFIRM | `04_フェーズP3_校正と一次解析.md:32-47` | FAIL: 結合検出 SNR0.5でm0 0.00/m10 0.01/mobs 0.01、SNR1.0で0.01/0.03/0.02（基準0.80）、FP 0.00（基準0.075以下でPASS）。陰性ハンディ全体平均+0.5044（`p5_report_values.csv:neg_gap_mean_overall`）。条件別平均 m0 +0.5163 / m10 +0.4878 / mobs +0.5092、中央値 0.5092/0.4939/0.5010 |
| P4 | 保存・破壊・統計 | `05_フェーズP4_頑健性と統計.md:7-25` | 未実施（ゲート失敗のため規定停止） |
| P5 | 失敗レポート | `06_フェーズP5_レポート提出.md:32-41` | `CALIBRATION_FAILED`、確認密封維持、pytest 32/32 |
| α | 非事前登録・探索（開発のみ） | `補足研究 α/研究骨子.md:19-25` | 列数/DGP/運用の分解（§2参照） |

判定5条件は現行 `PLAN.md:70-78` のまま（1.P-Rの95%CI上限<0、2.P-Sの95%CI上限<0、3.Pが100 sham中95パーセンタイルより良くGにも95%CIで優越、4.破壊で縮小・保存で符号維持、5.校正ゲート通過のAND）。

### 1.4 研究要旨と問いへの適合性再確認

要旨: 「物理特徴量を追加した時の予測精度向上は物理によるものか」。

適合する点:
- P=`f(X)` は全親 `X` から決定論的に作られ、`X` 条件付きで新情報を追加しない。よって `P-R` が改善しても「情報量」ではなく「表し方（帰納バイアス）」の効果しか測れない点を計画が明示している（§1.1）。「物理による」ことを現実大気の因果として主張せず、有限標本・指定モデル下の物理固有バイアスに限定する範囲設定は要旨と整合する。
- 対照の四層が要旨の「物理によるのか」に一対一で対応する: `P-R` は特徴工学上の利益の有無、`P-S`（100 sham中央値）は正しい物理式でなければ得られないかの検証、`P-G` は汎用非線形表現では代替できないかの検証、破壊（鉛直順序・符号破壊で効果消失）・保存（回転共変で符号維持）は物理内容への依存の検証、半合成 gate は測定器自体の感度・特異度の検証。5条件ANDでなければ「物理固有の優位は支持されない」とする規則のため、単なる精度向上を物理由来と誤読しない。
- 全群で追加列数・common mask・fit予算・seed・前処理を揃える約束により、差が「表し方」だけに帰着する設計である（情報量・次元・欠測・計算量の交絡排除）。

適合しない・限定が必要な点（要旨とのずれを防ぐため明記）:
- 一次束を core4（TI,N2,Ri_g,tke×@0）に縮小するため、原論文の12特徴束そのものの主張を直接反証・支持しない。core4一次の結論は「核心4種の物理表現」に限定し、12特徴全体への一般化は二次（top12/full24）の参考結果としてのみ扱う。報告書では「原論文の12特徴束とは範囲が異なる」と明記する。
- 一次は1時間先・RF・Perdigão・指定分割のみ。10分/3時間・ElasticNet/HGB・他地域・他季節・実運用有用性には拡張しない。二次は方向一致の参考に留め一次判定を覆さない。
- 推定は現実物理の因果効果ではない。BCA/ARIMA段を校正で省略（CAL-A4）し、本解析でも誤差構造の物理解釈は行わない。結論テンプレートは「物理固有の有限標本帰納バイアスを支持/不支持」に固定し、「物理が原因」「物理は不要」とは表現しない。
- OSF登録なしのため確証強度は一段低い（冒頭参照）。一次5条件を満たしても「内部凍結下での支持」に留め、「事前登録済み確証」とは記載しない。

以上により、要旨には当てはまるが、主張範囲を上記4点に限定した場合に限る。限定を外した表現は語弊となるため禁止表現（§F6）に含める。

### 1.3 群定義（現行の公称値）

- `R` 全親情報 44列、`P` は公称 `R`+物理12特徴×2lag=24列追加で合計68列、`S_j` は `R`+sham_j（j=1..100、各々Pと同追加列数。内訳 式シャッフル34/次元整合33/統計整合33）、`G` は `R`+汎用RFF/スプライン同列数（帯域は開発median heuristic、seed固定。現行sigma=6.539は開発実測の一例であり流用しない）。全群で追加列数・common mask・fit予算一致が約束（`現行研究 v1.0/PLAN.md:137-157`、`eli5_現行研究と補足α解説.md:63-68`）。ただし実装は§2.1の通りP_onlyだった点が主犯である。
- 一次モデル RF。フル格子は n_est 500固定×MF{0.3,0.7,1.0}×ML{5,20,100}×depth{None,12}=18点・seed5個（`configs/model_budget.yaml:2-16`）。校正の内側HPOはこのうち6点部分格子（MF{0.3,0.7}×ML{5,20,100}、depth None固定）でRのみ選択→P・Sへ勝者共通適用が一次（`scripts/p3_calibrate.py:236-240,243-268`）。群別同予算探索は感度扱い。
- master_seed `2026091501`、派生 `SHA256(master+namespace+index)` 先頭64bit（`01_実装構成と共通契約.md:51-55`）。

## 2. 失敗原因分析（追加研究への指摘を反映）

### 2.1 主犯: 校正プログラムの群定義欠落（P_only バグ）

ユーザー指摘の通り。確認済みコード位置:

- `現行研究 v1.0/perdigao_attribution/scripts/p3_calibrate.py:284-290` で `rf_p` を `Xp_tr`（物理24列のみ）で fit。docstring `p3_calibrate.py:18-20` の「Sham models use R+sham inputs（S=R+sham）」と非対称。
- 対する sham 側 `p3_calibrate.py:298-303` は `Xr+Xs`（R+sham）で fit。`G` 幅も `Xp.shape[1]` と同列数で生成（`p3_calibrate.py:393`）されるが、PがRを含まないため実質の入力次元・情報量が不一致になる。なお校正の検出判定自体は P-RとP-Sの両CI上限<0のみであり、Gは校正gate判定には使われない（Gは一次条件3の本解析用）。
- 報告「PはR+24」と実装「P=Xp24」の不一致は補足αで確定: `eli5_現行研究と補足α解説.md:134-138`「主犯は列数ではなく群定義欠落。`p3_calibrate.py:run_rep_fold` は P=Xp24 で fit、S=R+sham68 で fit」。

影響:

- 陰性ハンディが誇張: 全体平均 +0.5044（条件別 m0 +0.5163 / m10 +0.4878 / mobs +0.5092）は P_only の不利を含む。P_onlyではRの44列の親情報を欠くため、過剰適合以前に情報量不足の不利が生じる。
- 追加確認で RP（R+Xp、計画準拠）に直すと不利は縮小: パイロット n=5（mobs、quad+tanh、rho0.5、ridge、R_only、pool2、粒度0.2）で P_only full24 検出0.0/0.0・+0.4532 → RP full24 0.4(SNR0.5)/0.6(SNR1.0)・+0.0136（`完全版レポート.md:46-57`）。P_onlyは2列まで減らしても+0.43〜+0.90・検出0.0に張り付く。
- よって「試験失敗は24列追加だけが原因ではなく、P側プログラムが事前決定方法と不一致だったことも関係」と結論づける。RP化後も24列ハンディ自体は残る（r20で+0.0195）が、P_only時の約1/25に縮小する。

### 2.2 副因（αで分解済み・新研究で対処）

1. **列数過多（ただし主犯ではない）**: 本番 r20（mobs、quad+tanh、rho0.5、ridge、R_only、pool2、n=20、粒度0.05、Wilson 95%CI）で top6x2(12列追加) 検出 SNR0.5 0.6[0.387-0.781]/SNR1.0 0.9[0.699-0.972]・ハンディ0.016、core4x1(4列) 0.5[0.299-0.701]/0.75[0.531-0.888]・0.0108、full24 0.15[0.052-0.360]/0.35[0.181-0.567]・0.0195。点では12>4>24だがCI重なりのため順位確定不可、FP全部0.0（`完全版レポート.md:31-39`）。m0/m10のr20は未実施であり、mobsのみの結果である。500行級foldに24列は重いが、RP化後のハンディは0.01台に収まる。
2. **DGP単一**: 本番 r20（core4x1 RP、mobs）で quad 0.5[0.299-0.701]/0.75[0.531-0.888] vs linear 0.2[0.081-0.416]/0.45[0.258-0.658]（CI重なりあり）。cubic・regime・tanhなし・rho違い・smallRF・separate HPOはパイロット n=5（粒度0.2）の参考値であり確証ではない: cubic 0.0/0.0、regime 0.0/0.0、rho0.0 0.4/0.8・rho0.9 0.4/0.2で差小、smallRFはFP 0.2（1/5）に悪化のため不採用、separate HPOは大差なし（`完全版レポート.md:83-95`）。linear定義は z1+z2のみ＋tanh(/2)有界（quadは z1*z2+0.5*z1^2-0.5*z2^2、regimeはz1の4クラス×傾き0.15/0.6/1.0/1.5＋0.3*z1）。
3. **評価の保守性**: 開発は11断片日1133 issues・fold学習625/508行、日別4–276行と不均一（2017-02-03は4行）。2日プール評価（CAL-A1）は隣接14日 blocksより harsh（隣接転移ではSNR1.0で4/4日検出）。loo1は最小日4行でパイロット全15反復無効（n_valid 0）のため pool2維持。block7→3差なし。TOSTはSESOI 0.008862 m/sに対し日別CI平均幅 core4x1 0.0707/top6x2 0.0981/full24 0.1152で約8–13倍、幅∝1/√日と仮定した概算で700–1800日（約2–5年分）要し、季節性・自己相関を無視した参考値のため設計根拠には使わない（`完全版レポート.md:101-111`）。
4. **対照群の非対称**: 固定9-shamパネル中央値は単独fitより ensemble平滑で P-vs-S を保守化（`p3_calibrate.py:49-53` CAL-A3注記）。一次条件3（sham rank分布）がこれを補う設計だが、校正自体は9枚proxyだった。
5. 欠測は主犯ではない: 現行gate m0 0.00–0.01 / m10 0.01–0.04 / mobs 0.01–0.03で差小。ただしα本番r20はmobsのみであり、m0/m10のr20再評価は未実施のため「主犯否定」は参照値の再確認に留める。

## 3. 新研究 v1.1 の設計方針

### 3.1 変えない点（再実施の核）

- 問い・主張範囲・データ（536.011 v1.2のみ）・期間・分割（14日×8、purge 3h、右端揃え）・一次5条件・gate基準（検出0.80、FP0.075）・SESOI定義（開発BCA RMSEの1%、値は再計算）・fail-closed・clean-room・1コマンド再現。

### 3.2 変える点（amendment差分・事前固定）

| # | 修正 | 具体値 | 根拠 |
|---|---|---|---|
| F1 | **P群定義を R+Xp に修正** | `R`44、`P_core4`=R+(TI,N2,Ri_g,tke×@0のみ4列)=48を一次、`P_top12`=R+(TI,N2,Ri_g,Ri_f,tke,u_star_norm×@0,@-1の12列)=56を二次、`P_full24`=R+(12特徴×@0,@-1の24列)=68を二次、`S`=R+sham同追加列数、`G`=R+RFF/スプライン同追加列数。`run_rep_fold` は `[Xr,Xp]` 連結でscaler+fit（各群fold学習側で別fit）、単独Xp fitパス削除＋回帰テスト | §2.1主犯。報告と実装の一致。特徴名は `p3lib.py:50-63` の12特徴から固定 |
| F2 | **一次束を core4x1 に縮小** | 核心4種×@0のみ=4列追加。構成は凍結前に開発統計（分散・欠測率・カテゴリ重複回避）のみで確定し、確認性能で選ばない。親・十分統計量がRに無い特徴は補充せず `UNAVAILABLE` で落とす（現行PLAN§7継承）。top12/full24は二次に残す | α Q1。24列ハンディ回避。ただしr20の12>4順位はCI重なりで未確定のため、一次をcore4にする理由は「最小束でgate通過可能性を最大化する」であり「12列より優れる」ではない |
| F3 | **DGP複数化（事前固定3形）** | S形 quad / linear / regime（定義は§2.2-2の式、tanh(/2)有界ありを一次、なしは感度のみ）、SNR 0.25/0.5/0.75/1.0/1.5/2.0（gate判定は0.5/1.0のみ、他は報告のみ）、base ridge(alpha=1.0)のみ、HPO R_only 6点、rho 0.5固定（0.0/0.9は感度のみ）。cubic・smallRFは不採用 | α Q2。単一DGPの脆さ排除、smallRF不採用（FP悪化） |
| F4 | **校正を100-sham中央値に** | 9枚proxyを廃止し100枚中央値を一次判定に用いる。現行3.25h/1200反復（9-sham）から約8–11倍増のため、F4は段階実行とする：最小必須=core4×3DGP×SNR0.5/1.0×欠測3水準×100＋陰性100（=2100反復相当）を先行し、SNR拡張・top12/full24はcheckpoint分割で後行。資源上限（8CPU/16GB/10GB/壁24h）到達時は反復数削減でなく二次・図を省略し `n_valid` に記録（現行PLAN§11継承） | CAL-A3保守バイアス是正。工数§9参照 |
| F5 | **回帰テスト追加** | `total dim一致（R+Xp_total==R+sham_total==R+G_total）`、`added一致`、`common mask一致`、`P_only fit呼び出しでFAIL`、`RMSE/MAE名称照合（[0,3,4]でRMSE sqrt(25/3)・MAE 7/3）`、`時刻契約` をF1必須化 | 再発防止 |
| F6 | **新規内部凍結（OSFなし）** | 新tag `frozen-design-v1.1-YYYYMMDD`（YYYYMMDDは凍結日UTC）、新manifest、新bundle（ローカル保管・外部提出なし）。`receipt.md` は作らない。F3開始条件はP1_FROZEN＋tag/manifest一致のみ | 事前登録なしでも凍結証拠を残す。OSF文案（旧付録B）は廃止 |

運用は pool2・purge3h・block7維持。loo1・purge0・separate HPOは探索扱いで一次にしない。TOSTは参考のみ。

## 4. 固定仕様（凍結対象）

- R44内容（`p3lib.py:50-58` の22種5分値→lag展開で44列）・P12特徴式（`p3lib.py:60-63`）・主解析clip（開発0.5/99.5%ile。再現専用clip Ri_f∈[-5,5]・Ri_g<=5と区別）・分母フロア（開発絶対値下位1%以下は欠測）・QC（ldiag≠0除外、wake 310–340°除外。「除外なし」は感度扱い）・common mask（全群同一）・sham生成（式34/次元33/統計33、seed固定）・RF格子・seed派生・時刻契約（W=12、lags @0/@-1、purge 3h）は現行踏襲。core4/top12削減表は `p_subset.yaml` に開発統計理由付きで固定（例は04章・01章参照）。
- SESOIは開発BCA RMSE再計算の1%（現行値0.008862 m/sは参考、流用しない。BCAは rolling 24h窓ARIMA(2,0,1)再適合・100 origins・12-step・bias補正で推定し、expanding-historyは発散のため不採用という経緯を継承）。
- 70% complete-case gate（確認common-mask率が70%未満なら補完救済せずINFEASIBLE）、INFEASIBLE/CALIBRATION_FAILED/AUDIT_FAILED時の停止規則は現行 `PLAN.md:107-116` 踏襲。

## 5. AIコンテキストリセット前提のフェーズ設計

### 5.0 原則（全フェーズ共通）

1. **1セッション1フェーズ**。同じ長大チャットでP0→P5を通さない。
2. **source of truthはリポジトリ内ファイルのみ**。過去チャット・旧案フォルダは読まない。
3. 各セッション開始時に読むのは最大5点: `PLAN_v1.1.md`＋当該フェーズ手順＋`STATUS.md`＋直前handoff（F3以降はfreeze_manifest照合を追加。OSF receiptは存在しない）。
4. 各フェーズ終了時に必ず `pytest`＋`STATUS.md`更新＋`handoffs/PHASE_*.md`＋`NEXT_SESSION_PROMPT.md`上書き＋`git commit`。バックグラウンド残置なし。
5. 凍結後の設定変更・確認性能を見た後の調整・結果合わせ探索は禁止（fail-closedで `BLOCKED.json` に記録して停止）。
6. 長時間ジョブは `nohup caffeinate -dimsu ./scripts/run_phase.sh <PHASE> > logs/<PHASE>.console.log 2>&1 &`、5分に1回以下でJSON checkpoint、PID・再開点保存。

### 5.1 フェーズ一覧

```
F0 準備・分離(F0_DONE) → F1 P0環境(P0_COMPLETE) → F2 P1取得・凍結(P1_FROZEN)
→ F3 P2再現(P2_COMPLETE)
→ F4 P3校正ゲート(P3_COMPLETE or CALIBRATION_FAILED) → F5 P4頑健性(P4_COMPLETE or AUDIT_FAILED) → F6 P5報告・検収(DELIVERED)
※OSF登録フェーズなし。P1_FROZEN後は凍結検証のみでF3へ進む。
```

#### F0 準備・リポジトリ分離（新セッション1）

- 入力: 本計画書のみ。
- 実行: `perdigao_attribution_v1.1/` を独立git repo化、現行からの参照読み（configs/scripts/srcの写しを取る場合はSHA-256記録、生NetCDF・.venv・.gitは含めない）、`STATUS.md`（state=F0_DONE）、雛形（run_all.sh、pyproject）作成。
- 出力: `STATUS.md`、`handoffs/PHASE_F0.md`、`NEXT_SESSION_PROMPT.md`。
- 次への渡し文:
```text
作業ルートは <PC>/研究/広大シンポジウム/新研究 v1.1 です。
PLAN_v1.1.md、F1手順、perdigao_attribution_v1.1/STATUS.md、handoffs/PHASE_F0.mdだけを読んでP0だけを実行してください。旧研究・現行本体・過去チャットは参照しないでください。
```

#### F1 P0 環境・契約試験

- 入力: F0の4点。原論文XML/PDF・QCレポート・dataset metadata・著者commit `9420b71561d9d51c6665cab918371cd16fa074dd`（参照のみ）。
- 実行: Python 3.12 + uv.lock固定、paper_spec/code_spec抽出（6項目以上）、群定義回帰テスト（§3.2 F5）を含むsmoke test。`P dim==R+P_added` アサーション必須。
- 完了: `pytest`全合格、`STATUS.md=P0_COMPLETE`。

#### F2 P1 取得・監査・凍結

- 入力: F1の4点。確認標的の分布・相関・性能は読まない。
- 実行: DOI解決→Version 1.2取得→SHA-256/manifest→raw audit→塔tse13三者一致→70% gate→feature_dag（core4/full24併記、P=R+Xp明記）→protocol/model_budget/splits凍結→`freeze_manifest.json`＋`freeze_bundle.zip`（ローカル保管、外部提出なし）＋annotated tag `frozen-design-v1.1-YYYYMMDD`。
- 完了: `STATUS.md=P1_FROZEN`、git clean。F3へ進む前に凍結検証のみ行う（OSF照合なし）。

#### 凍結検証（OSFなし、AIが実施）

- OSF登録は行わない。F2完了後は `freeze_manifest.json` のSHA-256とgit tag `frozen-design-v1.1-YYYYMMDD` が一致することのみ確認し、一致すればF3へ進む。不一致・dirtyがあれば停止する。

#### F3 P2 原研究再現（凍結検証後）

- 開始条件: P1_FROZEN＋tag一致＋freeze_manifest一致（OSF照合なし。3点揃わなければ開始禁止）。
- 実行: R0/R1/R2各1回のみ、結果合わせ探索禁止。`reproduction_only=true` 列を付けP3/P4へ流用禁止。
- 出力: `tables/reproduction_results.csv`、`published_results.csv`、`audit/paper_code_concordance.csv`、`reports/reproduction.md`。

#### F4 P3 校正ゲート（本計画の核心）

- 開始条件: P2_COMPLETE＋git clean＋freeze一致。
- 実行順:
  1. freeze verification。
  2. 修正版 `run_rep_fold`（R+Xp連結、04章）で半合成 gate。一次は core4（合計48次元）。二次は top12（56）・full24（68）を別条件として実行。DGP 3形×SNR 6水準×欠測3水準×各100反復＋陰性100/条件（最小必須はSNR0.5/1.0のみでgate判定、SNR0.25/0.75/1.5/2.0は検出曲線の報告のみ）。検出/repは P-RとP-S両95%CI上限<0（日単位7日block bootstrap 10000回）。
  3. FAILなら実データ一次fitを開始せず `CALIBRATION_FAILED` でF6へ。PASS時のみ確認unsealし `runs/exposure.jsonl`（時刻・commit記録）作成→固定全群をcheckpoint付き実行。
- 出力: `tables/calibration_*.csv`、`reports/calibration.md`、`runs/<run_id>/checkpoint.json`。P3では結論自由記述禁止（JSON真偽のみ）。

#### F5 P4 頑健性・統計

- 開始条件: P3_COMPLETE（FAIL時は統計監査のみで追加解析なし）。
- 実行: 日単位 Δ_PR/Δ_PS、7日block bootstrap 10000回、sham rank、G優越、保存回転（30/90/137°）・破壊3系列（高度反転・浮力反転・shear破壊）、二次（10分/3時間、ElasticNet/HGB、レジーム、QC感度、Holm補正）。
- 出力: `tables/primary_results.csv` 等＋`primary_decision.json`（AND判定、後付け変更なし）＋`audit/statistical_audit.json`＋`leakage_audit.json`。

#### F6 P5 報告・検収

- 実行: 結果符号に依存しないテンプレートから `final_report.md/html/pdf` 生成（20章構成踏襲）、数値は表から自動転記、禁止表現（「物理は不要」「因果証明」等）排除、clean-room再実行（`uv sync --locked`＋`./run_all.sh --frozen --from-raw`、rtol1e-10/atol1e-12）、`delivery/` 集約。
- 完了: `STATUS.md=DELIVERED`（または理由付き例外）。`handoffs/PHASE_P5.md`＋`reports/提出物一覧.md` で停止。

### 5.2 コンテキスト切替チェックリスト（各セッション開始時・AI用）

- [ ] `git -C perdigao_attribution_v1.1 status --short` が想定状態か
- [ ] `STATUS.md` の state が前フェーズ完了を示すか
- [ ] freeze hash/tag と `freeze_manifest.json` が一致するか（OSF照合は行わない）
- [ ] `runs/exposure.jsonl` の有無が想定通りか（F4 PASS前は存在禁止）
- [ ] 現行 `現行研究 v1.0/perdigao_attribution/` に書込みがないか

## 6. 検証テスト（F1で必須、F4で再検証）

- 群次元: `assert Xrp_total == Xr_total + Xp_added` かつ `Xrs_total == Xrp_total` かつ `Xrg_total == Xrp_total`（totalはR込み、addedは物理/sham/G追加分）。core4一次では total 48 / added 4、top12では56/12、full24では68/24。
- P_only禁止: 単独Xp（例: 24列のみ）でfitする旧パスを呼ぶとテストがFAILする（旧 `run_rep_fold` のXp単独分岐を残さない）。
- 前処理: scaler（median/IQR）は各群・各fold学習側で別fitし、群間でパラメータ共有しない。RFにも同一前処理済み入力を渡す。
- 時刻: `max_input_time<=issue_time<target_start`、purge 3h（入力窓・標的窓とも境界越えなし）、右端揃え単体テスト。
- 指標: RMSE `sqrt(mean(err^2))` vs MAE `mean(abs(err))` fixture（[0,3,4]でRMSE sqrt(25/3)、MAE 7/3）、legacy呼称（`mean(sqrt(err^2))` をRMSEと呼ばない）検知。
- 密封: 確認target summaryを読もうとするとPermissionError（ガードテスト）。

## 7. 禁止・fail-closed

- 現行本体への書込み、tag/hashの流用・上書き、確認開封後の設計変更、DGP・seed・探索範囲の事後変更、SHAP/重要度/NN/追加データ、有料・承認要データの取得、著者コードのコピー再配布。
- 取得不能・列不足・gate不合格・低性能を理由に代替案へ自動遷移しない。`BLOCKED.json`（段階・例外・再開コマンド・hash）に保存して終了。

## 8. 成果物・検収

- `README.md`、`protocol.yaml`+freeze hash、`feature_dag.yaml`（P=R+Xp明記）＋`p_subset.yaml`、`environment/requirements.lock`、`manifests/*`、`tables/*.csv`（source of truth）、`figures/*`（+元CSV）、`reports/final_report.md/html/pdf`、`reproduction.md`、`paper_code_concordance.md`、`limitations.md`、`audit/*`、`handoffs/*`、`delivery/delivery_manifest.json`。
- 検収は `実装手順書_v1.1/08_最終検収チェックリスト.md` を全項目実測で埋める。未実施をPASSにしない。

## 9. 工数見積

- P3 gate現行実績: `.venv/bin/python scripts/p3_calibrate.py --sform quad` で約3.25h/1200反復（RF500本・HPO6点・9-sham、8CPU想定）。内訳は欠測3水準×（陽性3SNR＋陰性）×100。
- v1.1試算: 100-sham化でsham fitが約11倍（9→100）、DGP3形で約3倍、SNR6水準で約2倍。単純積算では24h超過のため、F4は最小必須（core4×3DGP×SNR0.5/1.0×3欠測×100＋陰性=2100反復相当）をcheckpoint分割で先行し、残りSNR・top12/full24は後行とする。8CPU/16GB/10GB/壁24h上限内で収まらなければ反復数削減でなく二次・図を省略し `n_valid` に記録。新規条件追加は `audit/log.jsonl` に理由を残す。
- P2再現約110分（`p2_reproduce.py`＋`p2_finalize.py`）。PDF視覚検査（空白・化け・切れ）必須。

## 付録A. 現行→新研究 差分表

| 項目 | 現行 v1.0 | 新研究 v1.1 | 備考 |
|---|---|---|---|
| P定義 | 公称R+24、実装Xp24（バグ） | 実装R+Xp（一次core4=48、二次full24=68） | 主犯修正 |
| 一次束 | full24 | core4x1 | α Q1 |
| DGP | quad単一、SNR3水準 | quad/linear/regime、SNR6水準 | α Q2 |
| sham校正 | 9枚proxy中央値 | 100枚中央値 | CAL-A3是正 |
| tag/hash | preregistered-design-20260915 / 794b1347…（OSF XETYJ登録済み） | 新tag `frozen-design-v1.1-YYYYMMDD` / 新hash（内部凍結のみ、OSFなし） | 外部登録なし |
| OSF | XETYJ（現行のみ） | なし（本研究では登録しない） | 内部凍結で代替、確証強度は一段低い |
| テスト | 32件 | ＋群定義5件以上 | 再発防止 |

## 付録B. OSFなし運用の記録方法（旧amendment文案は廃止）

- OSF登録を行わない代わりに、F2凍結時点で `freeze_manifest.json`＋`freeze_bundle.zip`（ローカル保管）＋annotated tag `frozen-design-v1.1-YYYYMMDD` を残し、`handoffs/PHASE_F2.md` にSHA-256・git commit・凍結UTCを記録する。
- 最終報告では「事前登録済み」「preregistered」と表現せず、「内部凍結準確証（OSF登録なし）」と明記する。査読・公表時は探索的再実行として扱う。
- 確認開封は `runs/exposure.jsonl`（時刻・commit記録）をもって証跡とし、開封後の設計変更は全面禁止とする。

## 出典

- `現行研究 v1.0/PLAN.md`、`MuseSpark1.3_実装手順書/00–08`、`perdigao_attribution/STATUS.md`、`reports/final_report.md`、`scripts/p3_calibrate.py:271-309`、`補足研究 α/研究骨子.md`、`追加実証の進め方.md`、`eli5_現行研究と補足α解説.md`。
