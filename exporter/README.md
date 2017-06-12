# Prometheus exporter for Sagemcom F@ST386 

This is a simple prometheus exporter to scrape metrics from the web interface of the
F@ST386.

It is hard-coded to:

- Port 8000
- Target IP `192.168.0.1`

## Dependencies

A recent python 2 or 3 version, plus:

```
pip install prometheus_client
```

