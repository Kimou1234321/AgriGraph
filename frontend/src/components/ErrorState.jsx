export default function ErrorState({ message = "Unable to load this view.", onRetry }) {
  return (
    <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
      <p>{message}</p>
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="mt-3 rounded bg-red-600 px-3 py-1.5 text-xs font-medium text-white"
        >
          Retry
        </button>
      ) : null}
    </div>
  );
}

