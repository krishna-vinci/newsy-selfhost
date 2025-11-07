import { toast } from 'svelte-sonner';

export function copyToClipboard(text: string, successMessage: string = 'Copied to clipboard!') {
	if (navigator.clipboard && window.isSecureContext) {
		navigator.clipboard.writeText(text)
			.then(() => toast.success(successMessage))
			.catch((err) => {
				toast.error('Failed to copy');
				console.error('Failed to copy: ', err);
			});
	} else {
		// Fallback for non-secure contexts
		const textArea = document.createElement('textarea');
		textArea.value = text;
		textArea.style.position = 'absolute';
		textArea.style.left = '-9999px';
		document.body.appendChild(textArea);
		textArea.select();
		try {
			document.execCommand('copy');
			toast.success(successMessage);
		} catch (err) {
			toast.error('Failed to copy');
			console.error('Failed to copy: ', err);
		} finally {
			document.body.removeChild(textArea);
		}
	}
}
