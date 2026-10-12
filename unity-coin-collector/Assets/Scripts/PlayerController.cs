using UnityEngine;

/// <summary>
/// Third-person movement for a Rigidbody player: WASD/arrows to move (relative to the camera),
/// Space to jump, Left Shift to sprint. Attach to a GameObject with a Rigidbody and a Collider.
/// </summary>
[RequireComponent(typeof(Rigidbody))]
public class PlayerController : MonoBehaviour
{
    [Header("Movement")]
    [SerializeField] float moveSpeed = 6f;
    [SerializeField] float sprintMultiplier = 1.6f;
    [SerializeField] float turnSpeed = 12f;

    [Header("Jumping")]
    [SerializeField] float jumpForce = 6f;
    [SerializeField] LayerMask groundLayers = ~0;
    [SerializeField] float groundCheckDistance = 0.2f;

    [Header("References")]
    [SerializeField] Transform cameraTransform;

    Rigidbody rb;
    Collider col;
    Vector3 moveInput;
    bool jumpQueued;

    void Awake()
    {
        rb = GetComponent<Rigidbody>();
        col = GetComponent<Collider>();
        rb.freezeRotation = true;
        rb.interpolation = RigidbodyInterpolation.Interpolate;
        if (cameraTransform == null && Camera.main != null) cameraTransform = Camera.main.transform;
    }

    void Update()
    {
        if (GameManager.Instance != null && GameManager.Instance.IsGameOver) { moveInput = Vector3.zero; return; }

        float h = Input.GetAxisRaw("Horizontal");
        float v = Input.GetAxisRaw("Vertical");

        // Move relative to where the camera is looking, flattened onto the ground.
        Vector3 forward = cameraTransform ? Vector3.ProjectOnPlane(cameraTransform.forward, Vector3.up).normalized : Vector3.forward;
        Vector3 right = cameraTransform ? Vector3.ProjectOnPlane(cameraTransform.right, Vector3.up).normalized : Vector3.right;
        moveInput = Vector3.ClampMagnitude(forward * v + right * h, 1f);

        if (Input.GetButtonDown("Jump") && IsGrounded()) jumpQueued = true;
    }

    void FixedUpdate()
    {
        float speed = moveSpeed * (Input.GetKey(KeyCode.LeftShift) ? sprintMultiplier : 1f);
        Vector3 targetVelocity = moveInput * speed;
        Vector3 velocity = rb.linearVelocity; // Unity 6 name (use rb.velocity in Unity 2022 and older)
        rb.linearVelocity = new Vector3(targetVelocity.x, velocity.y, targetVelocity.z);

        if (moveInput.sqrMagnitude > 0.01f)
        {
            Quaternion look = Quaternion.LookRotation(moveInput, Vector3.up);
            rb.MoveRotation(Quaternion.Slerp(rb.rotation, look, turnSpeed * Time.fixedDeltaTime));
        }

        if (jumpQueued)
        {
            rb.AddForce(Vector3.up * jumpForce, ForceMode.VelocityChange);
            jumpQueued = false;
        }
    }

    bool IsGrounded()
    {
        Vector3 origin = col.bounds.center;
        float distance = col.bounds.extents.y + groundCheckDistance;
        return Physics.Raycast(origin, Vector3.down, distance, groundLayers, QueryTriggerInteraction.Ignore);
    }
}
