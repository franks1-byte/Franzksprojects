using UnityEngine;

/// <summary>
/// A spinning, bobbing collectible. Needs a Collider set to "Is Trigger".
/// The player must be tagged "Player".
/// </summary>
public class Coin : MonoBehaviour
{
    [SerializeField] int value = 1;
    [SerializeField] float spinSpeed = 180f;
    [SerializeField] float bobHeight = 0.25f;
    [SerializeField] float bobSpeed = 2f;
    [SerializeField] AudioClip pickupSound;
    [SerializeField] GameObject pickupEffect;

    Vector3 startPos;
    float offset;

    void Start()
    {
        startPos = transform.position;
        offset = Random.Range(0f, Mathf.PI * 2f); // so coins don't bob in sync
        GameManager.Instance?.RegisterCoin();
    }

    void Update()
    {
        transform.Rotate(0f, spinSpeed * Time.deltaTime, 0f, Space.World);
        transform.position = startPos + Vector3.up * Mathf.Sin(Time.time * bobSpeed + offset) * bobHeight;
    }

    void OnTriggerEnter(Collider other)
    {
        if (!other.CompareTag("Player")) return;

        GameManager.Instance?.AddScore(value);
        if (pickupSound) AudioSource.PlayClipAtPoint(pickupSound, transform.position);
        if (pickupEffect) Destroy(Instantiate(pickupEffect, transform.position, Quaternion.identity), 2f);
        Destroy(gameObject);
    }
}
