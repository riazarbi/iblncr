# iblncr

A command line tool for rebalancing a portfolio of stocks and ETFs via [Interactive Brokers](https://www.interactivebrokers.com). 

## Basic usage

To use iblncr, install it with pipx:

```bash
pipx install git+https://github.com/riazarbi/iblncr.git
```

The Interactive Brokers API _only_ works with a locally installed, working Trader Workstatation or IB Gateway application. If you don't have one, you can use a headless docker image to run one.

You can either manually start the Docker container:

```bash
# in a separate terminal
docker run -it --rm --name broker  -p 4003:4003 ghcr.io/riazarbi/ib-headless:10.30.1t
```

Or use the built-in launch command:
```bash
iblncr launch
```
This will start the IB Gateway Docker container, and prompt you for your account type, username and password. You can use CTRL-C to stop it gracefully.


Once installed, you can run the iblncr in a separate terminal window with:

```bash
iblncr rebalance --account <account_number> --model <model_file> --port <port_number>
```

Argument defaults are as follows:

- account: None
- model: None, but there is a sample at iblncr/data/sample_model.yaml
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
poetry run iblncr rebalance --account <account_number> --model <model_file> --port <port_number>
```

## AI Code Generation

The code in this repo is based on an earlier R package I wrote called [rblncr](https://github.com/riazarbi/rblncr). I used [Cursor](https://www.cursor.com/) to refactor the R code into Python. 

The unit tests were written by [Cursor](https://www.cursor.com/).



