import sys

from crossword import *


class CrosswordCreator():

    def __init__(self, crossword):
        """
        Create new CSP crossword generate.
        """
        self.crossword = crossword
        self.domains = {
            var: self.crossword.words.copy()
            for var in self.crossword.variables
        }

    def letter_grid(self, assignment):
        """
        Return 2D array representing a given assignment.
        """
        letters = [
            [None for _ in range(self.crossword.width)]
            for _ in range(self.crossword.height)
        ]
        for variable, word in assignment.items():
            direction = variable.direction
            for k in range(len(word)):
                i = variable.i + (k if direction == Variable.DOWN else 0)
                j = variable.j + (k if direction == Variable.ACROSS else 0)
                letters[i][j] = word[k]
        return letters

    def print(self, assignment):
        """
        Print crossword assignment to the terminal.
        """
        letters = self.letter_grid(assignment)
        for i in range(self.crossword.height):
            for j in range(self.crossword.width):
                if self.crossword.structure[i][j]:
                    print(letters[i][j] or " ", end="")
                else:
                    print("█", end="")
            print()

    def save(self, assignment, filename):
        """
        Save crossword assignment to an image file.
        """
        from PIL import Image, ImageDraw, ImageFont
        cell_size = 100
        cell_border = 2
        interior_size = cell_size - 2 * cell_border
        letters = self.letter_grid(assignment)

        # Create a blank canvas
        img = Image.new(
            "RGBA",
            (self.crossword.width * cell_size,
             self.crossword.height * cell_size),
            "black"
        )
        font = ImageFont.truetype("assets/fonts/OpenSans-Regular.ttf", 80)
        draw = ImageDraw.Draw(img)

        for i in range(self.crossword.height):
            for j in range(self.crossword.width):

                rect = [
                    (j * cell_size + cell_border,
                     i * cell_size + cell_border),
                    ((j + 1) * cell_size - cell_border,
                     (i + 1) * cell_size - cell_border)
                ]
                if self.crossword.structure[i][j]:
                    draw.rectangle(rect, fill="white")
                    if letters[i][j]:
                        _, _, w, h = draw.textbbox((0, 0), letters[i][j], font=font)
                        draw.text(
                            (rect[0][0] + ((interior_size - w) / 2),
                             rect[0][1] + ((interior_size - h) / 2) - 10),
                            letters[i][j], fill="black", font=font
                        )

        img.save(filename)

    def solve(self):
        """
        Enforce node and arc consistency, and then solve the CSP.
        """
        self.enforce_node_consistency()
        self.ac3()
        return self.backtrack(dict())

    def enforce_node_consistency(self):
        """
        Update self.domains so each variable
        satisfies its unary length constraint.
        """

        for variable in self.domains:

            valid_words = set()

            for word in self.domains[variable]:
                if len(word) == variable.length:
                    valid_words.add(word)

            self.domains[variable] = valid_words
  
    def revise(self, x, y):
        """
        Make variable x arc consistent with variable y.
        Return True if the domain of x was revised.
        """

        overlap = self.crossword.overlaps[x, y]

        # No overlap means no revision is needed.
        if overlap is None:
            return False

        i, j = overlap
        revised = False

        # Iterate over a copy to safely remove words.
        for word_x in self.domains[x].copy():

            # Find whether at least one word in y is compatible.
            has_support = any(
                word_x[i] == word_y[j]
                for word_y in self.domains[y]
            )

            # Remove words without support.
            if not has_support:
                self.domains[x].remove(word_x)
                revised = True

        return revised
   
    def ac3(self, arcs=None):
        """
        Update self.domains such that each variable
        is arc consistent.

        Return False if any domain becomes empty.
        Return True otherwise.
        """

        from collections import deque

        # Initialize the queue of arcs.
        if arcs is None:
            queue = deque(
                (x, y)
                for x in self.crossword.variables
                for y in self.crossword.neighbors(x)
            )
        else:
            queue = deque(arcs)

        # Process arcs until the queue is empty.
        while queue:

            x, y = queue.popleft()

            # Revise the domain of x with respect to y.
            if self.revise(x, y):

                # No solution if x has no possible values.
                if len(self.domains[x]) == 0:
                    return False

                # Recheck arcs from other neighbors to x.
                for z in self.crossword.neighbors(x):
                    if z != y:
                        queue.append((z, x))

        return True
 
    def assignment_complete(self, assignment):
        """
        Return True if every crossword variable
        has been assigned a value.
        """

        return all(
            variable in assignment
            for variable in self.crossword.variables
        )

    def consistent(self, assignment):
        """
        Return True if assignment satisfies all constraints.
        Return False otherwise.
        """

        # 1. All assigned words must be different
        if len(set(assignment.values())) != len(assignment):
            return False

        # 2. Every word must have the correct length
        for variable, word in assignment.items():
            if len(word) != variable.length:
                return False

        # 3. Check overlapping letters
        for x in assignment:
            for y in assignment:

                if x == y:
                    continue

                overlap = self.crossword.overlaps[x, y]

                if overlap is None:
                    continue

                i, j = overlap

                if assignment[x][i] != assignment[y][j]:
                    return False

        return True

    def order_domain_values(self, var, assignment):
        """
        Return a list of words in the domain of var,
        ordered by the least-constraining-value heuristic.

        Words that eliminate fewer choices for unassigned
        neighboring variables appear first.
        """

        def ruled_out_values(word):

            eliminated = 0

            for neighbor in self.crossword.neighbors(var):

                # Ignore already assigned neighbors.
                if neighbor in assignment:
                    continue

                i, j = self.crossword.overlaps[var, neighbor]

                for neighbor_word in self.domains[neighbor]:

                    # Count words that conflict at the overlap.
                    if word[i] != neighbor_word[j]:
                        eliminated += 1

            return eliminated

        return sorted(
            self.domains[var],
            key=ruled_out_values
        )

    def select_unassigned_variable(self, assignment):
        """
        Select an unassigned variable using:

        1. Minimum Remaining Values (MRV)
        2. Degree Heuristic as a tie-breaker
        """

        # Identify variables without an assignment.
        unassigned = [
            variable
            for variable in self.crossword.variables
            if variable not in assignment
        ]

        # Select the variable with the smallest domain.
        # In case of a tie, prefer the highest degree.
        return min(
            unassigned,
            key=lambda variable: (
                len(self.domains[variable]),
                -len(self.crossword.neighbors(variable))
            )
        )
    
    def backtrack(self, assignment):
        """
        Use backtracking search to find a complete
        and consistent crossword assignment.

        Return the solution or None if no solution exists.
        """

        # Base case: all variables have been assigned.
        if self.assignment_complete(assignment):
            return assignment.copy()

        # Choose the next variable using MRV and Degree.
        var = self.select_unassigned_variable(assignment)

        # Try values using Least Constraining Value.
        for word in self.order_domain_values(var, assignment):

            # Make a tentative assignment.
            assignment[var] = word

            # Continue only if constraints are satisfied.
            if self.consistent(assignment):

                result = self.backtrack(assignment)

                # A complete solution was found.
                if result is not None:
                    return result

            # Undo the assignment and try another word.
            del assignment[var]

        # No candidate produced a valid solution.
        return None

def main():

    # Check usage
    if len(sys.argv) not in [3, 4]:
        sys.exit("Usage: python generate.py structure words [output]")

    # Parse command-line arguments
    structure = sys.argv[1]
    words = sys.argv[2]
    output = sys.argv[3] if len(sys.argv) == 4 else None

    # Generate crossword
    crossword = Crossword(structure, words)
    creator = CrosswordCreator(crossword)
    assignment = creator.solve()

    # Print result
    if assignment is None:
        print("No solution.")
    else:
        creator.print(assignment)
        if output:
            creator.save(assignment, output)


if __name__ == "__main__":
    main()
