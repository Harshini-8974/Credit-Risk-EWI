#input for agent1
import os

import mysql.connector
from dotenv import load_dotenv

load_dotenv()


def get_connection():
    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST"),
        port=int(os.getenv("MYSQL_PORT")),
        database=os.getenv("MYSQL_DB"),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD")
    )


def get_kpi_context(loan_acct_number, kpi_id):
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)

    query = """
        SELECT
            lc.LOAN_ACCT_NUMBER,
            lc.LOAN_TYPE,
            lc.LOAN_AMT,
            lc.OUTSTANDING_BAL,
            lc.REMAINING_TENURE_MONTHS,
            lc.INTEREST_RATE,
            lc.INTEREST_RATE_TYPE,
            lc.RISK_RANKING,
            lc.COLLATERAL_VALUE,
            lc.COLLATERAL_COVERAGE_PCT,
            lc.PRIMARY_CUSTOMER_NAME,
            lc.MCC,
            lc.TENURE_BUCKET,
            lc.REGION,
            lc.DDA_CNT_OVERALL,
            lc.DDA_COMBINED_AVG_BAL,
            lc.LIQUIDITY_RATIO,
            lc.AVG_OD_DAYS_CNT_6M,

            lk.KPI_ID,
            lk.KPI_NAME,
            lk.KPI_VALUE,
            lk.KPI_UNIT,
            lk.VALUES_IN_WINDOW,
            lk.OBSERVATION_WINDOW,
            lk.THRESHOLD_BREACHED,
            lk.ASSIGNED_TIER,

            kd.KPI_DESCRIPTION,
            kd.INTERPRETATION,
            kd.DIRECTIONALITY,
            kd.RISK_SIGNIFICANCE

        FROM loan_context lc

        JOIN loan_kpi_facts lk
            ON lc.LOAN_ACCT_NUMBER = lk.LOAN_ACCT_NUMBER

        JOIN kpi_definitions kd
            ON lk.KPI_ID = kd.KPI_ID

        WHERE lc.LOAN_ACCT_NUMBER = %s
          AND lk.KPI_ID = %s;
    """

    cursor.execute(query, (loan_acct_number, kpi_id))

    result = cursor.fetchone()

    cursor.close()
    connection.close()

    return result


def get_all_loan_accounts():
    connection = get_connection()
    cursor = connection.cursor()

    query = """
        SELECT DISTINCT LOAN_ACCT_NUMBER
        FROM loan_context;
    """

    cursor.execute(query)

    results = cursor.fetchall()

    cursor.close()
    connection.close()

    return [row[0] for row in results]


if __name__ == "__main__":
    loan_accounts = get_all_loan_accounts()

    print("Loan accounts:")

    for loan in loan_accounts:
        print(loan)