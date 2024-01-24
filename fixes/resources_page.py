from publish_script import Replacement, FixSet, Course, Page


class Fixes(FixSet):
    @classmethod
    def find_content(cls, course: 'Course') -> list['Page']:
        return course.get_pages_by_name('Student Support Resources')

    replacements = [
        Replacement(
            find=r'<p>(<strong>Your advisor.*)</p>',
            replace=r'''<p><strong>Your advisor</strong> can support you with any college policies or procedures and help inform you of and <a href="https://online.unity.edu/support/">support you with any of the college's resources.&nbsp;</a></p>''',
            tests=[
                Replacement.in_test(r'''<p><strong>Your advisor</strong> can support you with any college policies or procedures and help inform you of and <a href="https://online.unity.edu/support/">support you with any of the college's resources.&nbsp;</a></p>'''),
            ]
        ),
        Replacement(
            find=r'''<p><strong>TutorMe.*</p>''',
            replace=r'''<p><strong>Pear Deck Tutor (see TutorMe link in navigation)</strong>''' +
                    '''&nbsp;can support you with any course subject matter ''' +
                    '''or assessment specific question you may have.</p>''',
            tests=[
                Replacement.in_test('Pear Deck Tutor'),
                Replacement.not_in_test('<strong>TutorMe')
            ]
        ),
        Replacement(
            find=r"<p><strong>Your instructor.*<a.*</p>",
            replace=r'''<p><strong>Your instructor (click "Help" in Navbar and then "Ask instructor a question")''' +
                    r'''</strong>&nbsp;can support you with any course subject matter ''' +
                    r'''or assessment specific question you may have.</p>''',
            tests=[
                Replacement.not_in_test(r'''Your instructor (click "Help" in Navbar and then "Ask instructor ''' +
                                        '''a question")</strong>&nbsp;can support you with any college policies or ''' +
                                        '''procedures and help inform you of and <a href="https''' +
                                        '''://online.unity.edu/support/">support you with any of the college's ''' +
                                        '''resources.</a>''')
            ]
        ),
        Replacement(
            find=r'[.]</a>[.]</p>',
            replace=r'</a>.</p>',
            tests=[
                Replacement.not_in_test(r'.</a>.</p>')
            ]
        ),
        Replacement(
            find=r'matteror',
            replace=r'matter or',
            tests=[
                Replacement.not_in_test(r'matteror')
            ]
        )
    ]

