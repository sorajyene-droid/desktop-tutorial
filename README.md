# 板売買システム(先行構築 / order-book trading system)

株の板と同じルール(**価格優先・時間優先**の連続オークション)で動くマッチングエンジンを
中心にした、Python 製の取引システムの先行構築です。
※ 別プロジェクトの「配車ハブ(construction-system)」「日報MVP」とは**無関係**。

## 構成

| ファイル | 役割 |
|---|---|
| `engine.py` | 単一銘柄の板と約定(価格優先・時間優先の連続オークション) |
| `exchange.py` | 複数銘柄(銘柄ごとに `OrderBook`) |
| `login_auth.py` | ログイン認証。メール登録(形式チェック・小文字正規化)、bcrypt、5回失敗で5分ロック、JWT発行(有効期限つき) |
| `trade_auth.py` | 取引パスワード(発注時の本人確認)。bcrypt、5回失敗で60秒ロック |
| `balance.py` | 残高・与信。買い=代金ロック/売り=保有ロック/約定で受け渡し(差額返金)/キャンセルで解放 |
| `history.py` | 約定履歴、最終約定価格(時価)、ユーザーごとの平均取得単価 |
| `portfolio.py` | 時価評価+含み損益。時価=最終約定価格→無ければ取得単価→0 |
| `store.py` | 残高・保有・履歴を SQLite に保存/復元。**板(未約定注文)は永続化対象外** |
| `chart.py` | ローソク足(1m/5m/1h/1d/1w/1mo)、移動平均(SMA)、銘柄説明マスタ(SQLite) |
| `price_limit.py` | 値幅制限(ストップ高/安)。基準価格±割合(既定10%)or 定額。範囲外は `OrderRejected` |
| `secured_exchange.py` | 上記を束ねた本体。発注フロー全体を担う |
| `api.py` | FastAPI 層(HTTP + WebSocket) |
| `demo.html` | 板のみのブラウザ単体デモ |
| `demo-chart.html` | チャート版デモ(時間足切替・移動平均・銘柄説明・発注・板の live 更新) |

発注フロー(`secured_exchange.place_order`):
**ログイン確認 → 取引パスワード確認 → 値幅制限チェック → 残高ロック → 約定 → 受け渡し → 履歴記録 → 保存**

## セットアップ

```bash
pip install bcrypt PyJWT pytest fastapi "uvicorn[standard]" httpx cffi --break-system-packages
```

## テスト

```bash
python3 -m pytest -q     # 44 tests, all green
```

テストは使い捨ての一時ディレクトリ/DB(`tmp_path` フィクスチャ)で実行されます。

## API サーバー

JWT 署名鍵は環境変数から読みます(コードに固定値は書きません)。

```bash
export TRADING_SECRET_KEY=$(python3 -c "import secrets;print(secrets.token_hex(32))")
export TRADING_DB_PATH=./trading.db        # 任意。指定すると残高・履歴を永続化
uvicorn api:app
```

### エンドポイント

| Method | Path | 内容 |
|---|---|---|
| POST | `/register` | `{email, login_password, trade_password}` |
| POST | `/login` | `{email, login_password}` → `{token}` |
| POST | `/order` | ヘッダ `Authorization: Bearer <token>`、body `{trade_password, symbol, side, price, quantity}` |
| GET | `/depth/{symbol}` | 板 + 最終価格 |
| GET | `/chart/{symbol}?timeframe=1d` | ローソク足 + 移動平均(`candles_with_ma`) |
| GET | `/portfolio` | トークンで本人特定 → 現金・保有・評価額・含み損益 |
| GET | `/history/{symbol}` | 約定履歴 |
| GET | `/symbol/{symbol}` | 銘柄説明 |
| POST | `/price_limit` | 値幅制限の設定(任意) |
| WS | `/ws/{symbol}` | 接続時に板スナップショットを1回送信。以後その銘柄の発注・約定のたびに購読者全員へ push |

> 注: 入金/保有付与の HTTP エンドポイントは未提供です(`secured_exchange.deposit_cash` /
> `deposit_holding` をコードから呼ぶ前提)。必要なら管理用エンドポイントとして追加してください。

## 設計上の約束

1. 金額は整数(最小単位)で計算。浮動小数点で金額計算しない。
2. JWT 署名鍵は固定値をコードに書かず、環境変数 `TRADING_SECRET_KEY` から読む。
3. 認証の役割を混同しない:`login_auth`=誰として入るか、`trade_auth`=発注時の本人確認。
4. 板(未約定注文)は永続化していない。再起動後は板を立て直す前提。
5. テストは使い捨ての一時ディレクトリ/DB で行う。

## 次の作業候補

- [ ] **入金/保有付与の管理エンドポイント**(現状は `deposit_cash`/`deposit_holding` をコードから呼ぶ前提)
- [ ] **板(未約定注文)の永続化** — 現状は再起動で板が消える割り切り
- [ ] **注文種別の拡張** — 成行・逆指値・IOC/FOK など
- [ ] **手数料**(約定時の手数料計算と残高反映)
- [ ] `demo-chart.html` の銘柄説明を `SymbolInfoStore` と完全連動(現在は API 経由で取得済み)
- [ ] **本番DBを PostgreSQL に寄せる**(現状 SQLite)
- [ ] **メール確認・2FA** の実装(`login_auth` にフックあり)
- [ ] WebSocket の購読単位を複数銘柄/全板に拡張、再接続・heartbeat
- [ ] 法規制(扱う対象次第で金商法等)は技術と切り離して別途検討

---
### 完了済み(このリポジトリ時点)

- 11 モジュール + FastAPI 層(HTTP + WebSocket Hub)+ 2 デモ HTML
- `pytest -q` … **44 passed**
- `uvicorn api:app` で register→login→order が HTTP で通り、`/ws/{symbol}` で板・約定がリアルタイム配信されることを確認済み
