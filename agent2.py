from db import get_connection

def get_loan_risk_data(loan_acct_number):

    connection = get_connection()

    cursor = connection.cursor(dictionary=True)

    query = """
        SELECT
            lk.LOAN_ACCT_NUMBER,
            lk.KPI_ID,
            lk.KPI_NAME,
            lk.KPI_VALUE,
            lk.ASSIGNED_TIER,
            kd.THRESHOLD_AMBER,
            kd.THRESHOLD_RED,
            kd.THRESHOLD_CRITICAL,
            kd.DIRECTIONALITY,
            kd.KPI_WEIGHTAGE
        FROM loan_kpi_facts lk
        JOIN kpi_definitions kd
            ON lk.KPI_ID = kd.KPI_ID
        WHERE lk.LOAN_ACCT_NUMBER = %s
        ORDER BY lk.KPI_ID;
    """

    cursor.execute(query, (loan_acct_number,))
    result = cursor.fetchall()

    cursor.close()
    connection.close()

    return result

def get_severity_score(tier):

    if tier == "GREEN":
        return 0
    elif tier == "AMBER":
        return 1
    elif tier == "RED":
        return 2
    elif tier == "CRITICAL":
        return 3

    return 0

def calculate_composite_score(risk_data):

    total_weight = 0
    weighted_score = 0

    for row in risk_data:

        severity_score = get_severity_score(row["ASSIGNED_TIER"])

        weight = float(row["KPI_WEIGHTAGE"])

        weighted_score += severity_score * weight

        total_weight += weight

    if total_weight == 0:
        return 0.0

    normalized_score = weighted_score / total_weight

    risk_score = (normalized_score / 3) * 10

    return round(risk_score, 2)


def get_risk_category(risk_score):

    if risk_score <= 2.5:
        return "LOW"

    elif risk_score <= 5.0:
        return "MEDIUM"

    elif risk_score <= 7.5:
        return "HIGH"

    else:
        return "CRITICAL"


def agent2(state):

    loan_acct_number = state["loan_acct_number"]

    risk_data = get_loan_risk_data(loan_acct_number)

    risk_score = calculate_composite_score(risk_data)

    risk_category = get_risk_category(risk_score)

    return {
        "risk_score": risk_score,
        "risk_category": risk_category
    }

#testing block
if __name__ == "__main__":

    while True:

        loan_acct_number = input(
            "\nEnter loan account number (or type 'exit' to stop): "
        ).strip()

        if loan_acct_number.lower() == "exit":
            print("\nTesting stopped.")
            break

        if not loan_acct_number:
            print("Please enter a loan account number.")
            continue

        risk_data = get_loan_risk_data(loan_acct_number)

        if not risk_data:
            print("\nNo KPI data found for this loan.")
            continue

        risk_score = calculate_composite_score(risk_data)

        risk_category = get_risk_category(risk_score)

        print("=" * 25)
        print("RISK SUMMARY AGENT")
        print("=" * 25)
        print(f"LOAN ACCOUNT: {loan_acct_number}")
        print(f"RISK SCORE: {risk_score}")
        print(f"RISK CATEGORY: {risk_category}")
        print("=" * 25)

