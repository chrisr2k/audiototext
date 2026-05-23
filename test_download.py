"""Test downloading transcription results from OCI Object Storage."""
import json
import sys
import os

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.config import settings
from oci.signer import Signer
from oci.object_storage import ObjectStorageClient

signer = Signer(
    tenancy=settings.OCI_TENANCY_OCID,
    user=settings.OCI_USER_OCID,
    fingerprint=settings.OCI_FINGERPRINT,
    private_key_file_location=settings.OCI_PRIVATE_KEY_PATH,
)

config = {
    'user': settings.OCI_USER_OCID,
    'tenancy': settings.OCI_TENANCY_OCID,
    'fingerprint': settings.OCI_FINGERPRINT,
    'key_file': settings.OCI_PRIVATE_KEY_PATH,
    'region': settings.OCI_REGION,
}

client = ObjectStorageClient(config=config, signer=signer)

# List all objects in the bucket
objects = client.list_objects(
    namespace_name=settings.OCI_NAMESPACE,
    bucket_name=settings.OCI_BUCKET,
).data

print(f"Total objects in bucket: {len(objects.objects)}")
for obj in objects.objects:
    print(f"  - {obj.name}")

# Check the latest transcription result
print()
print("=== Checking latest transcription result ===")
for obj in reversed(objects.objects):
    if obj.name.endswith('.json'):
        print(f"Downloading: {obj.name}")
        response = client.get_object(
            namespace_name=settings.OCI_NAMESPACE,
            bucket_name=settings.OCI_BUCKET,
            object_name=obj.name,
        )
        data = json.loads(response.data.content)
        print(f"Status: {data.get('status')}")
        print(f"Transcriptions count: {len(data.get('transcriptions', []))}")
        for t in data.get('transcriptions', []):
            text = t.get('transcription', '')
            print(f"  Text: '{text}'")
            print(f"  Confidence: {t.get('confidence')}")
        break
