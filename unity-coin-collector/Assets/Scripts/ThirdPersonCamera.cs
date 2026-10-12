using UnityEngine;

/// <summary>
/// Orbit camera: hold the right mouse button and drag to look around, scroll to zoom.
/// Pulls in closer when a wall is between the camera and the player.
/// </summary>
public class ThirdPersonCamera : MonoBehaviour
{
    [SerializeField] Transform target;
    [SerializeField] Vector3 targetOffset = new Vector3(0f, 1.5f, 0f);
    [SerializeField] float distance = 6f;
    [SerializeField] float minDistance = 2f, maxDistance = 12f;
    [SerializeField] float mouseSensitivity = 3f;
    [SerializeField] float minPitch = -20f, maxPitch = 70f;
    [SerializeField] float smoothing = 10f;
    [SerializeField] LayerMask collisionLayers = ~0;

    float yaw, pitch = 20f;

    void LateUpdate()
    {
        if (!target) return;

        if (Input.GetMouseButton(1))
        {
            yaw += Input.GetAxis("Mouse X") * mouseSensitivity;
            pitch = Mathf.Clamp(pitch - Input.GetAxis("Mouse Y") * mouseSensitivity, minPitch, maxPitch);
        }
        distance = Mathf.Clamp(distance - Input.mouseScrollDelta.y, minDistance, maxDistance);

        Vector3 focus = target.position + targetOffset;
        Quaternion rotation = Quaternion.Euler(pitch, yaw, 0f);
        Vector3 desired = focus - rotation * Vector3.forward * distance;

        // Don't clip through walls.
        if (Physics.Linecast(focus, desired, out RaycastHit hit, collisionLayers, QueryTriggerInteraction.Ignore)
            && !hit.transform.IsChildOf(target))
            desired = hit.point + hit.normal * 0.2f;

        transform.position = Vector3.Lerp(transform.position, desired, smoothing * Time.deltaTime);
        transform.LookAt(focus);
    }
}
