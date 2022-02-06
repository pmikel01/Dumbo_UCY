Dumbo BFT. The code is forked from the implementation of Honeybadger protocols.

# HoneyBadgerBFT
The Honey Badger of BFT Protocols.

<img width=200 src="http://i.imgur.com/wqzdYl4.png"/>

[![Travis branch](https://img.shields.io/travis/initc3/HoneyBadgerBFT-Python/dev.svg)](https://travis-ci.org/initc3/HoneyBadgerBFT-Python)
[![Codecov branch](https://img.shields.io/codecov/c/github/initc3/honeybadgerbft-python/dev.svg)](https://codecov.io/github/initc3/honeybadgerbft-python?branch=dev)

HoneyBadgerBFT is a leaderless and completely asynchronous BFT consensus protocols.
This makes it a good fit for blockchains deployed over wide area networks
or when adversarial conditions are expected.
HoneyBadger nodes can even stay hidden behind anonymizing relays like Tor, and
the purely-asynchronous protocol will make progress at whatever rate the
network supports.

This repository contains a Python implementation of the HoneyBadgerBFT protocol.
It is still a prototype, and is not approved for production use. It is intended
to serve as a useful reference and alternative implementations for other projects.

## License
This is released under the CRAPL academic license. See ./CRAPL-LICENSE.txt
Other licenses may be issued at the authors' discretion.
