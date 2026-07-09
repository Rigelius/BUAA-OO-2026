public class Lexer {

    private String input;

    private int pos = 0;

    private String curToken;

    public Lexer(String input) {
        this.input = input;
        next();
    }

    public String peek() {
        return curToken;
    }

    public void next() {
        if (!hasNext()) {
            curToken = "EOF";
            return;
        }
        char c = input.charAt(pos);
        if (Character.isDigit(c)) {
            curToken = getNumber();
        } else if ("+-*^()x".indexOf(c) != -1) {
            pos++;
            curToken = String.valueOf(c);
        } else {
            pos++;
            next();
        }
    }

    public boolean hasNext() {
        return pos < input.length();
    }

    private String getNumber() {
        StringBuilder sb = new StringBuilder();
        while (hasNext() && Character.isDigit(input.charAt(pos))) {
            sb.append(input.charAt(pos));
            pos++;
        }
        return sb.toString();
    }
}