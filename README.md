# iblncr

Declarative stock portfolio management via [Interactive Brokers](https://www.interactivebrokers.com). 

Currently WIP

## System requirements

All you need is docker or some similar docker container runtime.

## Basic usage

TODO

## Under the hood

The Interactive Brokers API _only_ works with a locally installed, working Trader Workstatation or IB Gateway application. This project installs the IB Gateway inside a docker image and makes use of environment variables to log in and establish a connection. The python package then uses the ib_async python library to interact with the API.

From the bottom of the stack to the top:

- A base IB headless docker image from [riazarbi/ib-headless](https://github.com/riazarbi/ib-headless)
- Interactive Brokers [IB Gateway](https://www.interactivebrokers.com/en/trading/ibgateway-stable.php)
- [IBController](https://github.com/ib-controller/ib-controller) to automate Gateway launch and login
- [ib-async](https://github.com/ib-api-reloaded/ib_async) for interacting with the running Gateway
