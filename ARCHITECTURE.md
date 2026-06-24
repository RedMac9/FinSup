# FinSup2 Application Architecture

This document provides a high-level overview of the FinSup2 application's architecture.

## 1. Overview

FinSup2 is a Python-based financial analysis tool designed to fetch, process, and visualize stock market data. Its primary functions include retrieving data for various stock tickers, performing calculations (such as dividend analysis and market metrics), and generating outputs like graphs, Google Sheet updates, and Pushbullet notifications.

The architecture is modular, separating concerns into distinct components for data fetching, processing, and output generation.

## 2. Core Technologies

The application is built using the following key libraries:

-   **Data Fetching**: `yfinance`, `yahoo_fin`, `get-all-tickers`, `requests_html` are used to gather financial data from various online sources.
-   **Data Processing**: `pandas` and `numpy` are the workhorses for data manipulation, transformation, and numerical calculations.
-   **Visualization & UI**: `plotly` and `dash` are used to create interactive graphs and potentially serve a web-based dashboard.
-   **External Service Integrations**:
    -   `google-api-python-client`: To interact with Google services, primarily Google Sheets for data output.
    -   `pushbullet.py`: To send real-time notifications.
-   **File I/O**: `openpyxl` is used for reading from and writing to Excel files.

## 3. Directory Structure

The project is organized into several key directories under the `app/` folder:

-   `app/main.py`: The main entry point for the application.
-   `app/api/`: Contains code related to exposing application functionality, possibly via a Dash-based API.
-   `app/core/`: Handles application-wide configuration and setup.
-   `app/dividends/`: A dedicated module for all logic related to dividend data, including fetching, calculating, and transforming it.
-   `app/services/`: Contains the core business logic and integrations with external services. This includes market metric calculations, and handlers for Pushbullet and Google Sheets.
-   `app/output/`: Modules responsible for generating the final output of the application, such as graphs (`graph.py`) and Google Sheet data (`gsheet.py`).
-   `app/schemas/`: Defines data structures or schemas, likely for internal data validation and consistency.
-   `app/tickers_lists/`: Manages the lists and groups of stock tickers that the application will analyze.
-   `tests/`: Contains various test scripts to validate application functionality.

## 4. Execution Flow

The application generally follows this data flow:

1.  **Configuration**: On startup, configuration is loaded from `app/core/config.py`, which likely reads sensitive data from `secrets.env`.
2.  **Ticker Selection**: A list of stock tickers is retrieved from the `app/tickers_lists/` module.
3.  **Data Ingestion**: The `dividends` and `services` modules use libraries like `yfinance` to fetch raw financial data for the selected tickers.
4.  **Data Processing**: The raw data is processed using `pandas`. The core logic in the `services` and `dividends` modules calculates various metrics.
5.  **Output Generation**: The processed data is passed to the `output` modules, which use `plotly` to generate graphs and `google-api-python-client` to update Google Sheets.
6.  **Notification**: If configured, the `services/daily_pushbullet.py` service sends a notification about the results.
7.  **User Interface (Optional)**: If a `dash` server is initiated (likely from `app/main.py`), it serves a web interface displaying the visualizations.

## 5. Configuration & Secrets

-   **`secrets.env`**: This file stores sensitive information like API keys and credentials. It should not be committed to version control.
-   **`app/core/config.py`**: This file is likely responsible for loading the variables from `secrets.env` and making them available to the rest of the application.
