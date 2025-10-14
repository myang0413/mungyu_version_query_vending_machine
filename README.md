# Text-to-SQL Demo App

This is a demo application that converts natural language questions into SQL queries for the DVD Rental database.

## How to Run

1.  **Start the database:**
    ```bash
    cd database
    docker-compose up -d --build
    ```

2.  **Set up environment variables:**
    - Rename `.env.example` to `.env`.
    - Add your OpenAI API key to the `.env` file.

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Run the Streamlit app:**
    ```bash
    streamlit run main.py
    ```
