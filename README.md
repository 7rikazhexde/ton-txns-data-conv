# ton-txns-data-conv

English | [日本語](README_ja.md)

The TON Transactions data converter is a project aimed at retrieving and converting transaction data recorded on the TON blockchain.

## Table of contents

- [ton-txns-data-conv](#ton-txns-data-conv)
  - [Table of contents](#table-of-contents)
  - [Usage](#usage)
    - [Install](#install)
      - [Setup for poetry](#setup-for-poetry)
      - [Setup for virtualenv](#setup-for-virtualenv)
    - [Project settings](#project-settings)
  - [Feature](#feature)
    - [Get all transaction information](#get-all-transaction-information)
    - [Creating custom files for cryptact](#creating-custom-files-for-cryptact)
    - [Visualize TON Whales Staking Amount History](#visualize-ton-whales-staking-amount-history)
  - [Disclaimer](#disclaimer)

## Usage

> [!IMPORTANT]
> This project uses `TON API` and `pytonapi`, `pytoniq_core`.
>
> Please check below for details.
> - <https://tonapi.io/>
> - <https://github.com/tonkeeper/pytonapi>
> - <https://github.com/yungwine/pytoniq>

### Install

```bash
git clone https://github.com/7rikazhexde/ton-txns-data-conv.git
```

#### Setup for poetry

```bash
poetry install --without dev
```

If you use development-dependent packages, do the following.

```bash
poetry install
```

#### Setup for virtualenv

venv, pyenv virtualenv, etc.

```bash
pip install -r requirements.txt
```

If you use development-dependent packages, do the following.

```bash
pip install -r requirements.txt requirements-dev.txt
```

### Project settings

Edit [config.toml](./ton_txns_data_conv/config.toml) with your user information for the project.  
This file contains settings for your `TON API key`[^1], TON address, and file saving options.  
[^1]: Required when using pytonapi library.  
      Please check for details <https://docs.tonconsole.com/tonapi>

## Feature

### Get all transaction information

Use `TON API` to get all the transactitions data associated with the address.

```bash
python get_ton_txns_api.py
```

### Creating custom files for cryptact

[get_ton_transactions.py](./ton_txns_data_conv/get_ton_transactions.py) to create a custom file for Cryptact from the acquired transactions data.

> [!CAUTION]
> - The CSV file is created in the custom file format for staking rewards in Cryptact. Refer to <https://support.cryptact.com/hc/en-us/articles/360002571312-Custom-File-for-any-other-trades#menu210> for more information on the custom file format.  
> - Only transactions with a value greater than 0 in the `in_msg` field are included in the CSV file.  
> - In the TON blockchain, there are no specific key/value pairs to distinguish between staking rewards and other transactions. Therefore, the CSV file may include transactions from other wallets that are not related to staking. Please manually remove any non-staking related data from the CSV file.  

```bash
python create_ton_stkrwd_cryptact_custom.py
```

### Visualize TON Whales Staking Amount History

Use [ton_whales_staking_dashboard.py](./ton_txns_data_conv/ton_whales_staking_dashboard.py) to visualize and analyze the staking amount history for TON Whales.

![TON Whales Staking Amount History Dashboard](.other_data/TON%20Whales%20Staking%20Amount%20History.png)
*Screenshot of the TON Whales Staking Amount History Dashboard*

```bash
python ton_whales_staking_dashboard.py
```

This script creates a Dash web application that allows you to:

- Fetch and display staking data for a specified date range
- Visualize the staking amount history in a graph
- Save staking reward history as a CSV file
- View helpful tooltips for input fields

> [!IMPORTANT]
> - The timezone in this script is set to Japan Standard Time (JST). If you're in a different timezone, you need to modify the `timezone_offset` in the `config.toml` file to match your local timezone.
> - The script uses the TON Whales staking pool by default. If you're using a different staking pool, make sure to update the pool address in the `config.toml` file.
> - The CSV files generated by this script are named with a detailed format including the date range, adjust value, and number of records. This helps in distinguishing between different data sets and parameters used.

> [!TIP]
> - Use the "Go Staking Stats" button to open your TON Whales staking statistics in a new browser tab.
> - Hover over the question mark icons (?) next to input fields for tooltips. These provide important information about how to use each field and how staking rewards are calculated.
> - The "Staking Pool Member Address" field has a tooltip explaining how to find the correct address to use, including a link to the TON Whales Staking page that opens in a new tab.

## Disclaimer

- While it has been confirmed that it is possible to retrieve transaction data related to a specific TON address, the accuracy of the data cannot be guaranteed.
- Please use this code at your own risk. The authors of this project are not responsible for any damages caused by the use of this code.
- The specifications of TONAPI and the data format of Cryptact may change, so please check the latest information.
- Transaction history depends on the transaction status. Please ensure that the acquired data is accurate and error-free by verifying the transaction data.
- The staking reward calculation in `ton_whales_staking_dashboard.py` is based on changes in the staked amount and may not perfectly reflect all reward distributions. Always cross-verify the results with official sources.
- The user interface of `ton_whales_staking_dashboard.py` includes tooltips to provide additional information. While these are designed to be helpful, always refer to official TON documentation for the most up-to-date and accurate information.
