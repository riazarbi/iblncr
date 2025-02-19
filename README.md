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
git clone git@github.com:riazarbi/iblncr.git
cd iblncr
pipx install .
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

