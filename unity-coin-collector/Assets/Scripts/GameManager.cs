using UnityEngine;
using UnityEngine.SceneManagement;
using TMPro;

/// <summary>
/// Tracks score and the countdown timer, and shows win/lose screens.
/// Put one in the scene and assign the TextMeshPro UI references.
/// </summary>
public class GameManager : MonoBehaviour
{
    public static GameManager Instance { get; private set; }

    [SerializeField] float timeLimit = 60f;

    [Header("UI (TextMeshPro)")]
    [SerializeField] TMP_Text scoreText;
    [SerializeField] TMP_Text timerText;
    [SerializeField] GameObject endPanel;
    [SerializeField] TMP_Text endTitle;

    public bool IsGameOver { get; private set; }

    int score;
    int totalCoins;
    float timeLeft;

    void Awake()
    {
        if (Instance != null && Instance != this) { Destroy(gameObject); return; }
        Instance = this;
        timeLeft = timeLimit;
        if (endPanel) endPanel.SetActive(false);
    }

    public void RegisterCoin()
    {
        totalCoins++;
        UpdateUI();
    }

    public void AddScore(int amount)
    {
        if (IsGameOver) return;
        score += amount;
        UpdateUI();
        if (score >= totalCoins) EndGame(true);
    }

    void Update()
    {
        if (IsGameOver)
        {
            if (Input.GetKeyDown(KeyCode.R)) SceneManager.LoadScene(SceneManager.GetActiveScene().buildIndex);
            return;
        }

        timeLeft -= Time.deltaTime;
        if (timeLeft <= 0f) { timeLeft = 0f; EndGame(false); }
        UpdateUI();
    }

    void UpdateUI()
    {
        if (scoreText) scoreText.text = $"Coins: {score} / {totalCoins}";
        if (timerText)
        {
            timerText.text = $"{Mathf.CeilToInt(timeLeft)}s";
            timerText.color = timeLeft < 10f ? Color.red : Color.white;
        }
    }

    void EndGame(bool won)
    {
        IsGameOver = true;
        if (endPanel) endPanel.SetActive(true);
        if (endTitle) endTitle.text = won ? $"You win!\n{Mathf.CeilToInt(timeLimit - timeLeft)}s\n\nPress R to play again"
                                          : $"Time's up!\n{score} / {totalCoins} coins\n\nPress R to try again";
    }
}
