# iblncr

A command line tool for rebalancing a portfolio of stocks and ETFs via [Interactive Brokers](https://www.interactivebrokers.com). 

## Basic usage

The Interactive Brokers API _only_ works with a locally installed, working Trader Workstatation or IB Gateway application. If you don't have one, you can use a headless docker image to run one.

```bash
# in a separate terminal
docker run -it --rm --name broker  -p 4003:4003 ghcr.io/riazarbi/ib-headless:10.30.1t
```
Install iblncr with pipx:

```bash
 pipx install git+https://github.com/riazarbi/iblncr.git
```

Once installed, you can run the application with:

```bash
iblncr --account <account_number> --model <model_file> --port <port_number>
```

Argument defaults are as follows:

- account: None
- model: iblncr/data/sample_model.yaml
- port: 4003

If you don't specify an account, the application will list the available accounts given by the API and prompt you to select one.

## Development

To run the tests:

```bash
poetry install --with dev
poetry run pytest
```

To run the application:

```bash
poetry run iblncr --account <account_number> --model <model_file> --port <port_number>
```

## AI Code Generation

The code in this repo is based on an earlier R package I wrote called [rblncr](https://github.com/riazarbi/rblncr). I used [Cursor](https://www.cursor.com/) to refactor the R code into Python. 

The unit tests were written by [Cursor](https://www.cursor.com/).



