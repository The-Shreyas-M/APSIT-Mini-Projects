async function checkReview() {
    const review = document.getElementById('reviewText').value;
    const resultElement = document.getElementById('result');

    if (!review) {
        alert("Please enter a review.");
        return;
    }

    // Show loading text
    resultElement.innerText = "Processing...";
    resultElement.style.color = "#FFA500";  // Orange for processing

    try {
        const response = await fetch('/check_review', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                model: "mistral-nemo:latest",
                prompt: `Analyze the following review and determine if it is fake or real.

Consider:
- Length & coherence
- Human errors (typos, grammar)
- Exaggeration or promotional tone
- Language patterns & emotional tone
- Review history indicators
- Excessive praise or criticism
- Lack of specific details

Provide:
1. A probability score (0-100%).
2. A clear verdict: **"Fake", "Cannot Determine", or "Real"**.
3. A brief explanation supporting your conclusion.
"
 "${review}"`,
                stream: false
            })
        });

        const data = await response.json();
        resultElement.innerText = data.response || "No response received.";
        resultElement.style.color = "#000000";  // Green for success

    } catch (error) {
        console.error("Error:", error);
        resultElement.innerText = "Error processing request.";
        resultElement.style.color = "#FF5733";  // Red for error
    }
}
