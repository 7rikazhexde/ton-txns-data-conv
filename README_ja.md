# ton-txns-data-conv

[English](README.md) | 日本語

TON トランザクションデータコンバーターは、TONブロックチェーンに記録されたトランザクションデータを取得し変換することを目的としたプロジェクトです。

## 目次

- [ton-txns-data-conv](#ton-txns-data-conv)
  - [目次](#目次)
  - [使用方法](#使用方法)
    - [インストール](#インストール)
      - [poetryのセットアップ](#poetryのセットアップ)
      - [virtualenvのセットアップ](#virtualenvのセットアップ)
    - [プロジェクト設定](#プロジェクト設定)
  - [機能](#機能)
    - [全トランザクション情報の取得](#全トランザクション情報の取得)
    - [cryptact用カスタムファイルの作成](#cryptact用カスタムファイルの作成)
    - [TON Whalesのステーキング報酬履歴の可視化](#ton-whalesのステーキング報酬履歴の可視化)
  - [免責事項](#免責事項)

## 使用方法

> [!IMPORTANT]
> このプロジェクトでは以下のプロジェクトを使用しています。
>
> - `TON API`: <https://tonapi.io/>
> - `pytonapi`: <https://github.com/tonkeeper/pytonapi>
> - `pytoniq_core`: <https://github.com/yungwine/pytoniq>
> - `TON Index(API V3)`: <https://toncenter.com/api/v3/>
> - `ton-api-v4`: <https://github.com/ton-community/ton-api-v4>

### インストール

```bash
git clone https://github.com/7rikazhexde/ton-txns-data-conv.git
```

#### poetryのセットアップ

```bash
poetry install --without dev
```

開発依存パッケージを使用する場合は、以下を実行してください。

```bash
poetry install
```

#### virtualenvのセットアップ

venv、pyenv virtualenv など

```bash
pip install -r requirements.txt
```

開発依存パッケージを使用する場合は、以下を実行してください。

```bash
pip install -r requirements.txt requirements-dev.txt
```

### プロジェクト設定

プロジェクトのユーザー情報を[config.toml](./ton_txns_data_conv/config.toml)で編集してください。
このファイルには、`TON APIキー`[^1]、TONアドレス、ファイル保存オプションの設定が含まれています。
[^1]: pytonapiライブラリを使用する際に必要ですが、最新版コードでは`TON Index(API V3)`に変更しているため将来的に削除する可能性があります。
      詳細は <https://docs.tonconsole.com/tonapi> をご確認ください。

## 機能

### 全トランザクション情報の取得

`TON Index(API V3)`を使用して、アドレス(`user_friendly_address`)に関連する取引データを指定された期間分(`transaction_history_period`:デフォルト365日)取得する

```bash
python get_ton_txns_api.py
```

### cryptact用カスタムファイルの作成

[get_ton_transactions.py](./ton_txns_data_conv/get_ton_transactions.py)を使用して、取得したトランザクションデータからCryptact用のカスタムファイルを作成します。

> [!CAUTION]
> - CSVファイルは、Cryptactのステーキング報酬用カスタムファイル形式で作成されます。カスタムファイル形式の詳細については、<https://support.cryptact.com/hc/ja/articles/360002571312-%E3%82%AB%E3%82%B9%E3%82%BF%E3%83%A0%E3%83%95%E3%82%A1%E3%82%A4%E3%83%AB%E3%81%AE%E4%BD%9C%E6%88%90%E6%96%B9%E6%B3%95#h_01GXMK12D426VV4S6GAJHV9T2B> を参照してください。
> - `in_msg`フィールドの値が0より大きいトランザクションのみがCSVファイルに含まれます。
> - TONブロックチェーンでは、ステーキング報酬と他のトランザクションを区別するための特定のキー/値ペアがありません。そのため、CSVファイルにはステーキングに関連しない他のウォレットからのトランザクションが含まれる可能性があります。CSVファイルからステーキングに関連しないデータを手動で削除してください。

```bash
python create_ton_stkrwd_cryptact_custom.py
```

### TON Whalesのステーキング報酬履歴の可視化

[ton_whales_staking_dashboard.py](./ton_txns_data_conv/ton_whales_staking_dashboard.py)を使用して、TON Whalesのステーキング報酬履歴を可視化・分析します。

![TON Whalesステーキング報酬履歴ダッシュボード](.other_data/TON%20Whales%20Staking%20Amount%20History.png)
*TON Whalesステーキング報酬履歴ダッシュボードのスクリーンショット*

```bash
python ton_whales_staking_dashboard.py
```

このスクリプトは以下の機能を持つDashウェブアプリケーションを作成します：

- 指定した日付範囲のステーキングデータの取得と表示
- グラフでのステーキング報酬履歴の可視化
- ステーキング報酬履歴のCSVファイルとしての保存
- 入力フィールドの有用なツールチップの表示

> [!IMPORTANT]
> - このスクリプトのタイムゾーンは日本標準時（JST / UTC+9:00）に設定されています。異なるタイムゾーンにいる場合は、`config.toml`ファイルの`local_timezone`を現地のタイムゾーンに合わせて修正する必要があります。
> - スクリプトはデフォルトでTON Whalesステーキングプールを使用します。異なるステーキングプールを使用している場合は、`config.toml`ファイルのプールアドレスを更新してください。
> - このスクリプトで生成されるCSVファイルは、日付範囲、調整値、レコード数を含む詳細な形式で名前が付けられます。これにより、異なるデータセットと使用されたパラメータを区別するのに役立ちます。

> [!TIP]
> - "Go Staking Stats"ボタンを使用して、新しいブラウザタブでTON Whalesのステーキング統計を開くことができます。
> - 入力フィールドの隣にある疑問符アイコン（?）にカーソルを合わせると、ツールチップが表示されます。これらは各フィールドの使用方法とステーキング報酬の計算方法に関する重要な情報を提供します。
> - "Staking Pool Member Address"フィールドには、正しいアドレスの見つけ方を説明するツールチップがあり、新しいタブで開くTON Whalesステーキングページへのリンクも含まれています。

## 免責事項

- 特定のTONアドレスに関連するトランザクションデータを取得できることは確認されていますが、データの正確性は保証できません。
- このコードは自己責任で使用してください。このプロジェクトの作者は、このコードの使用によって生じたいかなる損害についても責任を負いません。
- TONAPIの仕様やCryptactのデータ形式は変更される可能性があるため、最新の情報を確認してください。
- トランザクション履歴はトランザクションの状態に依存します。トランザクションデータを確認して、取得したデータが正確でエラーがないことを確認してください。
- `ton_whales_staking_dashboard.py`のステーキング報酬計算は、ステーキング報酬の変化に基づいており、全ての報酬配布を完全に反映していない可能性があります。結果は常に公式のソースと照合して確認してください。
- `ton_whales_staking_dashboard.py`のユーザーインターフェースには、追加情報を提供するツールチップが含まれています。これらは役立つように設計されていますが、最新かつ正確な情報については常に公式のTONドキュメントを参照してください。
