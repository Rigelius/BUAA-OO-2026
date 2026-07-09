import java.util.Scanner;

public class MainClass {
    public static void main(String[] args) {
        Scanner sc = new Scanner(System.in);
        String s = sc.nextLine();
        s = Processor.preprocess(s);
        Lexer lexer = new Lexer(s);
        Parser parser = new Parser(lexer);
        Expr expr = parser.parseExpr();
        Poly poly = expr.toPoly();
        poly.mergeLikeTerms();
        System.out.println(poly);
    }
}