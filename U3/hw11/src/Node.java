public class Node<T> {

    private final T value;
    private Node<T> prev;
    private Node<T> next;

    public Node(T value) {
        this.value = value;
        this.prev = null;
        this.next = null;
    }

    public void insertBefore(Node<T> newNode) {
        setPrev(newNode.getPrev());
        setNext(newNode);
        if (newNode.getPrev() != null) {
            newNode.getPrev().setNext(this);
        }
        newNode.setPrev(this);
    }

    public void remove() {
        if (prev != null) {
            prev.setNext(next);
        }
        if (next != null) {
            next.setPrev(prev);
        }
        setPrev(null);
        setNext(null);
    }

    public T getValue() {
        return value;
    }

    public Node<T> getPrev() {
        return prev;
    }

    public void setPrev(Node<T> prev) {
        this.prev = prev;
    }

    public Node<T> getNext() {
        return next;
    }

    public void setNext(Node<T> next) {
        this.next = next;
    }
}
