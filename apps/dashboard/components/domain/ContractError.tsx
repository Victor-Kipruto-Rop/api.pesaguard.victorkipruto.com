export function ContractError({ message }: { message: string }) {
  return <section className="panel empty-state" role="alert"><p>Unable to load backend data</p><span>{message}</span></section>;
}
